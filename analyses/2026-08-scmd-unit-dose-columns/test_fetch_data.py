from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import fetch_data as fetch
import pytest

PAYLOAD = b"vmp_snomed_code,unit_dose_uom\n123,tablet\n"


def fake_urlopen(_url: str) -> MagicMock:
    mock = MagicMock()
    mock.__enter__.return_value = BytesIO(PAYLOAD)
    mock.__exit__.return_value = False
    return mock


def test_downloads_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch.urllib.request, "urlopen", fake_urlopen)
    target = tmp_path / "data" / "scmd.csv"

    assert fetch.fetch_scmd(target=target) == target
    assert target.read_bytes() == PAYLOAD


def test_skips_download_when_file_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_urlopen(_url: str) -> None:
        raise AssertionError("download must not run when the file exists")

    monkeypatch.setattr(fetch.urllib.request, "urlopen", fail_urlopen)
    target = tmp_path / "scmd.csv"
    target.write_bytes(b"existing")

    assert fetch.fetch_scmd(target=target) == target
    assert target.read_bytes() == b"existing"
