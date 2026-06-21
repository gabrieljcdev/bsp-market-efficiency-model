"""Single lightweight request to detect whether RP's 406 block has cleared.
Prints just the HTTP status code (or ERR). Fresh NetworkClient each call so
the refresh-token mints a current access token. Run from scripts/."""
import os
import sys

sys.path.insert(0, os.path.expanduser('~/projects/racing_project/vendor/rpscrape/scripts'))
from dotenv import load_dotenv

load_dotenv(os.path.expanduser('~/projects/racing_project/vendor/rpscrape/.env'))
from utils.network import NetworkClient

try:
    nc = NetworkClient(email=os.getenv('EMAIL'), access_token=os.getenv('ACCESS_TOKEN'))
    # _session_get returns the response without the 7x 406 retry loop.
    resp = nc._session_get('https://www.racingpost.com/results/2024-01-01', True)
    print(resp.status_code)
except Exception as e:
    print('ERR', type(e).__name__)
