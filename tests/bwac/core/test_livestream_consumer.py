import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from bwac.core.livestream_consumer import LivestreamConsumer, open_files


BASE = {
    "courseOverGround": 42.9, 
    "latitude": 59.729342, 
    "longitude": 5.481622,
    "rateOfTurn": 0, 
    "shipType": 30, 
    "speedOverGround": 12.1,
    "trueHeading": 42, 
    "navigationalStatus": 0, 
    "mmsi": 257719900,
    "msgtime": "2026-04-20T00:00:00+00:00",
}

CASES = [
    ("clean",               "TITANIC"),
    ("embedded_comma",      "6AZGSUN,@H@A@C"),        # original bug
    ("embedded_quote",      'SHIP "FOO" BAR'),     
    ("embedded_newline",    "LINE1\nLINE2"),         
    ("comma_and_quote",     'RANDOM, "NAME"'),        # both comma and quote
    ("all_at_padding",      "@" * 20),                # unnamed vessel
    ("empty",               ""),                    
    ("unicode",             "BJØRNØYA Ærlig"),        # non-ASCII
]


def run_consumer(tmp_path: Path, messages: list[dict]) -> Path:
    """testing oiut LivestreamConsumer.get_data against a fake stream! """
    fake_response = MagicMock()
    fake_response.iter_lines.return_value = [json.dumps(m).encode("utf-8") for m in messages]
    fake_response.__enter__ = lambda s: s
    fake_response.__exit__ = lambda *a: None

    open_files.clear()
    consumer = LivestreamConsumer()
    with patch("bwac.core.livestream_consumer.requests.Session") as SessionCls:
        SessionCls.return_value.get.return_value = fake_response
        try:
            consumer.get_data(access_token="dummy", timeout_in_s=3600, output_dir=tmp_path)
        except RuntimeError as e:
            if "timeout after" not in str(e):
                raise

    for fp, _ in open_files.values():
        fp.flush()

    out = tmp_path / "AIS_2026_04_20.csv"
    assert out.exists(), "expected output CSV was not created"
    return out


def test_csv_fix(tmp_path: Path):
    messages = [dict(BASE, name=name) for _, name in CASES]
    out = run_consumer(tmp_path, messages)

    with out.open(newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == len(CASES), f"expected {len(CASES)} rows, got {len(rows)}"
    for (label, expected_name), row in zip(CASES, rows):
        assert row["name"] == expected_name, (
            f"[{label}] name failed, seeing {row['name']!r}, expected {expected_name!r}"
        )
        assert row["mmsi"] == str(BASE["mmsi"]), f"[{label}] mmsi corrupted"
    print(f".csv-file ends up correctly stored for {len(CASES)} name variants")


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        test_csv_fix(Path(tmp))