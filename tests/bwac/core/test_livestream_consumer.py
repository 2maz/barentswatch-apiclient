import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
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


def run_consumer(tmp_path: Path, messages: list[dict]) -> Path:
    """LivestreamConsumer.get_data against fake stream """
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
    assert out.exists(), "the expected output .csv-file was not created"
    return out
    

@pytest.mark.parametrize(
    ["label", "name"],
    [
        ("clean",            "TITANIC"),
        ("embedded_comma",   "6AZGSUN,@H@A@C"),        # original bug
        ("embedded_quote",   'SHIP "FOO" BAR'),
        ("embedded_newline", "LINE1\nLINE2"),
        ("comma_and_quote",  'RANDOM, "NAME"'),
        ("all_at_padding",   "@" * 20),                # unnamed vessel
        ("empty",            ""),
        ("unicode",          "BJØRNØYA Ærlig"),        # non-ASCII
    ],
)
def test_name_roundtrips(label, name, tmp_path):
    message = dict(BASE, name=name)
    out = run_consumer(tmp_path, [message])

    with out.open(newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1, f"[{label}] expected 1 row, got {len(rows)}"
    assert rows[0]["name"] == name, (
        f"[{label}] name round-trip failed: got {rows[0]['name']!r}, expected {name!r}"
    )
    assert rows[0]["mmsi"] == str(BASE["mmsi"]), f"[{label}] mmsi corrupted"
