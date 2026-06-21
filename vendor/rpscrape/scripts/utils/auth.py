"""Cognito access-token auto-refresh for Racing Post.

RP issues a short-lived (~30 min) Cognito access token and a long-lived
(~30 day) refresh token. With the refresh token we can mint fresh access
tokens headlessly via InitiateAuth/REFRESH_TOKEN_AUTH (no client secret),
so a long scrape does not need the 30-min cookie babysat.

Capture the refresh token ONCE from browser cookies (the key ending in
`.refreshToken`) and put it in .env as REFRESH_TOKEN. ACCESS_TOKEN then
becomes optional (used only as a warm-start until the first refresh).
"""

import base64
import json
import os
import time

from curl_cffi import requests


COGNITO_REGION = 'eu-west-1'
CLIENT_ID = '3fii107m4bmtggnm21pud2es21'
COGNITO_URL = f'https://cognito-idp.{COGNITO_REGION}.amazonaws.com/'


def decode_exp(token: str | None) -> int:
    """Unix expiry from a JWT access token, or 0 if undecodable."""
    if not token:
        return 0
    try:
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)  # pad base64url
        data = json.loads(base64.urlsafe_b64decode(payload))
        return int(data.get('exp', 0))
    except Exception:
        return 0


class TokenManager:
    def __init__(
        self,
        refresh_token: str | None = None,
        access_token: str | None = None,
        skew: int = 120,
    ) -> None:
        self.refresh_token = refresh_token or os.getenv('REFRESH_TOKEN')
        self._access_token = access_token or os.getenv('ACCESS_TOKEN')
        self._exp = decode_exp(self._access_token)
        self.skew = skew  # refresh this many seconds before expiry

    @property
    def enabled(self) -> bool:
        return bool(self.refresh_token)

    def _refresh(self) -> str:
        if not self.refresh_token:
            raise RuntimeError('No REFRESH_TOKEN set; cannot auto-refresh.')

        r = requests.post(
            COGNITO_URL,
            headers={
                'Content-Type': 'application/x-amz-json-1.1',
                'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth',
            },
            json={
                'ClientId': CLIENT_ID,
                'AuthFlow': 'REFRESH_TOKEN_AUTH',
                'AuthParameters': {'REFRESH_TOKEN': self.refresh_token},
            },
            impersonate='chrome',
            timeout=20,
        )
        if r.status_code != 200:
            raise RuntimeError(f'Cognito refresh failed {r.status_code}: {r.text[:200]}')

        result = r.json()['AuthenticationResult']
        self._access_token = result['AccessToken']
        # Prefer the JWT's own exp; fall back to ExpiresIn.
        self._exp = decode_exp(self._access_token) or (
            int(time.time()) + int(result.get('ExpiresIn', 1800))
        )
        return self._access_token

    def get(self) -> str | None:
        """Return a valid access token, refreshing if expired/near-expiry."""
        if self.refresh_token and (
            not self._access_token or time.time() >= self._exp - self.skew
        ):
            self._refresh()
        return self._access_token
