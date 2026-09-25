import csv
import datetime as dt
import json
import logging
import time
from pathlib import Path
from typing import Any

import requests

from bwac.core.access import Access
from bwac.core.constants import BARENTS_WATCH_LIVE_AIS_URL
from bwac.utils import read_timestamp

logger = logging.getLogger(__name__)

# Example data: b{"courseOverGround":268,"latitude":66.004573,"longitude":8.029767,"name":"TRANSOCEAN ENCOURAGE","rateOfTurn":-3,"shipType":90,"speedOverGround":0,"trueHeading":225,"navigationalStatus":3,"mmsi":258627000,"msgtime":"2025-07-24T10:14:50+00:00"}'

last_day = None
timeout_in_s = 0

MAX_RETRY_DELAY_S = 60

CONNECT_TIMEOUT_S = 10
# no bytes at all for this long -> requests raises ReadTimeout
READ_TIMEOUT_S = 60
# stream is alive (keep-alives arrive) but delivers no AIS message for this long
STALL_TIMEOUT_S = 60


class TokenRenewalRequired(RuntimeError):
    """The access token used for the current stream is about to expire."""


class StreamStalled(RuntimeError):
    """The stream is still open, but stopped delivering AIS messages."""


class LivestreamConsumer:
    timeout_in_s: int
    open_files: dict[str, Any]

    def __init__(self):
        self.timeout_in_s = 0
        self.open_files = {}
        # backoff delay used for retrying after connection/stream errors -
        # kept separate from timeout_in_s, which tracks the (much larger)
        # token-expiry driven reconnect window and must not be conflated
        # with retry backoff (see wait_for_timeout).
        self.retry_delay_s = 0

    def wait_for_timeout(self):
        """
        Create a timeout that increase on recurrent failure
        """
        # continued calls to timeout shall increase wait time
        self.retry_delay_s = min(self.retry_delay_s + 5, MAX_RETRY_DELAY_S)
        time.sleep(self.retry_delay_s)

    def reset_retry_delay(self):
        """
        Reset the retry backoff after a succesful reconnection
        """
        self.retry_delay_s = 0

    def get_data(
        self,
        access_token: str,
        timeout_in_s: int = 3500,
        output_dir: Path | str | None = None,
        stall_timeout_in_s: int = STALL_TIMEOUT_S,
    ):
        if output_dir is None:
            output_dir = Path()
        else:
            output_dir = Path(output_dir)
            if not output_dir.exists():
                output_dir.mkdir(parents=True, exist_ok=True)

        self.timeout_in_s = timeout_in_s

        session = requests.Session()
        headers = {"Authorization": f"Bearer {access_token}"}

        start_time = time.monotonic()
        last_message_time = start_time
        with session.get(
            url=BARENTS_WATCH_LIVE_AIS_URL, headers=headers, stream=True,
            # (connect timeout, read timeout) - without this a stalled
            # connection that never closes and never sends bytes blocks
            # iter_lines() forever, bypassing the checks below
            timeout=(CONNECT_TIMEOUT_S, READ_TIMEOUT_S),
            params={
                "modelType": "Full",
                "modelFormat": "Json",
            }
        ) as response:
            # an error response (e.g. 401 on an expired token) has no AIS
            # messages - fail here instead of silently draining an empty body
            response.raise_for_status()

            for idx, line in enumerate(response.iter_lines()):
                now = time.monotonic()
                if line:
                    last_message_time = now
                    # messages arrive, so the connection is established
                    self.reset_retry_delay()

                    data = json.loads(line.decode("UTF-8"))

                    timestamp = read_timestamp(data["msgtime"])
                    day = timestamp.strftime("%Y_%m_%d")
                    path = output_dir / f"AIS_{day}.csv"

                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=dt.timezone.utc)

                    # considering maximum 2h delay
                    if (
                        len(self.open_files) == 2
                        and (
                            dt.datetime.now(tz=dt.timezone.utc) - timestamp
                        ).total_seconds()
                        > 7200
                    ):
                        prev_day_filename = min(self.open_files.keys())
                        fp, _ = self.open_files[prev_day_filename]
                        fp.close()
                        del self.open_files[prev_day_filename]


                    if path not in self.open_files or self.open_files[str(path)][0].closed:
                        write_header = not path.exists()
                        fp = open(path, "a", newline="") # noqa
                        writer = csv.DictWriter(fp, fieldnames=list(data.keys()), quoting=csv.QUOTE_MINIMAL)
                        self.open_files[str(path)] = (fp, writer)
                        if write_header:
                            writer.writeheader()

                    fp, writer = self.open_files[str(path)]
                    writer.writerow(data)
                    fp.flush()

                    print(
                        f"Processed {idx} message - current day: {day} -- (token used since: {int(now - start_time)} s, renewal after: {self.timeout_in_s} s)",
                        end="\r",
                        flush=True,
                    )

                # keep-alive lines carry no message - the checks below must run
                # for those as well, otherwise a stream that only sends
                # keep-alives keeps this loop spinning forever: no reconnect,
                # no token renewal and frozen progress output
                if now - last_message_time >= stall_timeout_in_s:
                    raise StreamStalled(
                        f"Consumer.get_data: no message received for {int(now - last_message_time)} seconds"
                    )
                if now - start_time >= self.timeout_in_s:
                    raise TokenRenewalRequired(
                        f"Consumer.get_data: timeout after {self.timeout_in_s} seconds"
                    )

    def start(self, output_dir: Path | str | None = None):
        access = Access()
        while True:
            try:
                access.acquire()
                # reconnect ahead of the actual expiry, so that the stream is
                # never re-established with an already rejected token
                self.get_data(
                    access.access_token,
                    max(access.expires_in - 100, 60),
                    output_dir=output_dir,
                )
                # server closed the stream without an error
                logger.warning("Stream closed by server - reconnecting")
                self.wait_for_timeout()
            except TokenRenewalRequired:
                # deliberate proactive reconnect ahead of token expiry -
                # the stream was healthy, so do not back off
                self.reset_retry_delay()
            except Exception as e:
                logger.warning(f"Stream error - reconnecting: {e}")
                self.wait_for_timeout()
            finally:
                for fp, _ in self.open_files.values():
                    if not fp.closed:
                        fp.close()
                self.open_files.clear()
