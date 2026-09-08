from pathlib import Path

from google.cloud import bigquery
from google.oauth2.service_account import Credentials

PROJECT_ID = "ebmdatalab"
LOCATION = "EU"

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CREDENTIALS_PATH = REPO_ROOT / "bq-service-account.json"


def get_bigquery_client() -> bigquery.Client:
    credentials = Credentials.from_service_account_file(DEFAULT_CREDENTIALS_PATH)
    return bigquery.Client(
        project=PROJECT_ID, credentials=credentials, location=LOCATION
    )
