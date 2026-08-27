import argparse
import shutil
import urllib.request
from pathlib import Path

TARGET = Path(__file__).resolve().parent / "data" / "scmd_provisional_202606.csv"
DOWNLOAD_URL = (
    "https://opendata.nhsbsa.net/dataset/"
    "74f3e468-095b-44c0-b957-f3766a92514e/resource/"
    "5f83f6bf-ee5d-4698-9c50-3ac464a92b11/download/scmd_provisional_202606.csv"
)


def fetch_scmd(target: Path = TARGET, force: bool = False) -> Path:
    """Return the local CSV path. Download only when missing or forced."""
    if target.exists() and not force:
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(DOWNLOAD_URL) as response, target.open("wb") as out:
        shutil.copyfileobj(response, out)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download the June 2026 provisional SCMD extract when missing."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Download even when the local file already exists.",
    )
    args = parser.parse_args()
    print(fetch_scmd(force=args.force))


if __name__ == "__main__":
    main()
