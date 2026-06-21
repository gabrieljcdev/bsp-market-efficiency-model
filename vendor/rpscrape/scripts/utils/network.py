from collections.abc import Sequence
from curl_cffi import Session, Response, BrowserTypeLiteral
from curl_cffi.requests.exceptions import RequestException
from curl_cffi.curl import CurlError
from random import choice
from time import sleep
from urllib.parse import quote

from utils.auth import TokenManager


# Transient network failures we should retry rather than crash on.
NET_ERRORS = (RequestException, CurlError)


class Persistent406Error(Exception):
    pass


BROWSERS: Sequence[BrowserTypeLiteral] = (
    'edge',
    'chrome',
    'firefox',
    'safari',
)


COGNITO_POOL = '3fii107m4bmtggnm21pud2es21'


def construct_cookies(email: str | None, access_token: str | None) -> dict[str, str]:
    if email is None or access_token is None:
        return {}

    key = f'CognitoIdentityServiceProvider.{COGNITO_POOL}.{quote(email, safe="")}.accessToken'

    return {
        key: access_token,
    }


class NetworkClient:
    def __init__(
        self,
        *,
        email: str | None = None,
        access_token: str | None = None,
        timeout: int = 14,
    ) -> None:
        self.email = email

        # If a REFRESH_TOKEN is available, mint/rotate access tokens headlessly.
        # Otherwise fall back to the static access_token (legacy behaviour).
        self.token_manager: TokenManager | None = TokenManager(access_token=access_token)
        if not self.token_manager.enabled:
            self.token_manager = None

        token = self.token_manager.get() if self.token_manager else access_token
        self._current_token = token
        cookies = construct_cookies(email, token)

        self.session: Session = Session(impersonate=choice(BROWSERS), cookies=cookies)
        self.timeout: int = timeout

        self._set_cookies()

    def _set_cookies(self) -> None:
        _ = self.session.get('https://www.racingpost.com/api/auth/set-cookies')

    def _maybe_refresh(self) -> None:
        """Rotate the cognito cookie + re-handshake if the token changed."""
        if self.token_manager is None:
            return
        token = self.token_manager.get()
        if token and token != self._current_token:
            key = (
                f'CognitoIdentityServiceProvider.{COGNITO_POOL}.'
                f'{quote(self.email or "", safe="")}.accessToken'
            )
            self.session.cookies.set(key, token)
            self._current_token = token
            self._set_cookies()

    def _session_get(
        self,
        url: str,
        allow_redirects: bool,
        attempts: int = 8,
        base: float = 2.0,
        cap: float = 60.0,
    ) -> Response:
        """session.get with retry + exponential backoff on transient
        network errors (timeouts, connection resets). Re-raises only after
        the backoff budget is exhausted (~3 min), which outlasts brief
        server-side throttling rather than crashing the whole run."""
        for i in range(1, attempts + 1):
            try:
                return self.session.get(
                    url,
                    allow_redirects=allow_redirects,
                    timeout=self.timeout,
                )
            except NET_ERRORS:
                if i >= attempts:
                    raise
                sleep(min(base * (2 ** (i - 1)), cap))

    def get(
        self,
        url: str,
        allow_redirects: bool = True,
        retries: int = 7,
        delay: float = 1.4,
    ) -> tuple[int, Response]:
        self._maybe_refresh()
        for attempt in range(1, retries):
            response = self._session_get(url, allow_redirects)

            if response.status_code != 406:
                return response.status_code, response

            if attempt < retries:
                sleep(delay)

        raise Persistent406Error(f'received 406 for {retries} attempts on {url}')
