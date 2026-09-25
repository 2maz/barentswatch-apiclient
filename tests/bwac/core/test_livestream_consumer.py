import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from bwac.core.livestream_consumer import (
    LivestreamConsumer,
    StreamStalled,
    TokenRenewalRequired,
)

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

    consumer = LivestreamConsumer()
    with patch("bwac.core.livestream_consumer.requests.Session") as SessionCls:
        SessionCls.return_value.get.return_value = fake_response
        try:
            consumer.get_data(access_token="dummy", timeout_in_s=3600, output_dir=tmp_path)
        except RuntimeError as e:
            if "timeout after" not in str(e):
                raise

    for fp, _ in consumer.open_files.values():
        if not fp.closed:
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


def test_retry_backoff_independent_of_token_timeout(monkeypatch):
    """wait_for_timeout() must not sleep for anywhere near the token-expiry
    window (self.timeout_in_s, typically ~3600s) after a stream/connection
    error - it should use its own small, capped backoff counter."""
    sleep_calls = []
    monkeypatch.setattr(
        "bwac.core.livestream_consumer.time.sleep", lambda s: sleep_calls.append(s)
    )

    consumer = LivestreamConsumer()
    consumer.timeout_in_s = 3600  # set as get_data() would ahead of a real token

    consumer.wait_for_timeout()

    assert sleep_calls[0] < 60, (
        f"retry backoff slept for {sleep_calls[0]}s - it is using the token "
        "expiry window instead of an independent, capped backoff"
    )


def test_retry_backoff_is_capped(monkeypatch):
    monkeypatch.setattr("bwac.core.livestream_consumer.time.sleep", lambda s: None)

    consumer = LivestreamConsumer()
    for _ in range(50):
        consumer.wait_for_timeout()

    assert consumer.retry_delay_s <= 60


def stream_consumer(monkeypatch, lines: list[bytes], clock_step_s: int):
    """LivestreamConsumer.get_data against a fake stream, with a fake clock
    that advances by clock_step_s on every read of the monotonic time."""
    ticks = iter(range(0, 10**6, clock_step_s))
    monkeypatch.setattr(
        "bwac.core.livestream_consumer.time.monotonic", lambda: next(ticks)
    )

    fake_response = MagicMock()
    fake_response.iter_lines.return_value = iter(lines)
    fake_response.__enter__ = lambda s: s
    fake_response.__exit__ = lambda *a: None

    consumer = LivestreamConsumer()
    with patch("bwac.core.livestream_consumer.requests.Session") as SessionCls:
        SessionCls.return_value.get.return_value = fake_response
        consumer.get_data(access_token="dummy", timeout_in_s=3600)


def test_keep_alive_only_stream_raises_stalled(monkeypatch, tmp_path):
    """A stream that stays open but only sends keep-alive (empty) lines must
    not block the loop forever - it has to be detected and reconnected."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(StreamStalled):
        # 10s per line, far more keep-alives than the stall timeout covers
        stream_consumer(monkeypatch, [b""] * 100, clock_step_s=10)


def test_token_renewal_checked_on_keep_alive_lines(monkeypatch, tmp_path):
    """The token expiry deadline must be checked on keep-alive lines as well,
    otherwise a quiet stream keeps using a token beyond its lifetime."""
    monkeypatch.chdir(tmp_path)

    # one message per 50s keeps the stall detection satisfied; at 10s per line
    # the 3600s deadline is crossed on line 359, which is a keep-alive
    message = json.dumps(dict(BASE, name="TITANIC")).encode("utf-8")
    lines = ([message] + [b""] * 4) * 72
    assert len(lines) == 360 and lines[-1] == b"", (
        "the deadline has to be crossed on the last, keep-alive line"
    )

    with pytest.raises(TokenRenewalRequired):
        stream_consumer(monkeypatch, lines, clock_step_s=10)


def test_error_response_is_not_treated_as_empty_stream(tmp_path):
    """A non-200 response (e.g. 401 on an expired token) must raise instead of
    returning silently, which would reconnect in a tight loop."""
    fake_response = MagicMock()
    fake_response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
    fake_response.__enter__ = lambda s: s
    fake_response.__exit__ = lambda *a: None

    consumer = LivestreamConsumer()
    with patch("bwac.core.livestream_consumer.requests.Session") as SessionCls:
        SessionCls.return_value.get.return_value = fake_response
        with pytest.raises(requests.HTTPError):
            consumer.get_data(access_token="dummy", timeout_in_s=3600, output_dir=tmp_path)


def test_request_uses_read_timeout():
    """Without a read timeout a silent connection blocks iter_lines forever."""
    fake_response = MagicMock()
    fake_response.iter_lines.return_value = iter([])
    fake_response.__enter__ = lambda s: s
    fake_response.__exit__ = lambda *a: None

    consumer = LivestreamConsumer()
    with patch("bwac.core.livestream_consumer.requests.Session") as SessionCls:
        SessionCls.return_value.get.return_value = fake_response
        consumer.get_data(access_token="dummy", timeout_in_s=3600)

    _, kwargs = SessionCls.return_value.get.call_args
    connect_timeout, read_timeout = kwargs["timeout"]
    assert connect_timeout > 0 and read_timeout > 0
