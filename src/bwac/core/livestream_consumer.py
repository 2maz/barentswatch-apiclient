import csv
import datetime as dt
import json
import logging
import time
from pathlib import Path

import requests

from bwac.core.access import Access
from bwac.core.constants import BARENTS_WATCH_LIVE_AIS_URL
from bwac.utils import read_timestamp

logger = logging.getLogger(__name__)

# Example data: b{"courseOverGround":268,"latitude":66.004573,"longitude":8.029767,"name":"TRANSOCEAN ENCOURAGE","rateOfTurn":-3,"shipType":90,"speedOverGround":0,"trueHeading":225,"navigationalStatus":3,"mmsi":258627000,"msgtime":"2025-07-24T10:14:50+00:00"}'

class LivestreamConsumer:
    timeout_in_s: int
    open_files: dict[str, any]

    def __init__(self):
        self.timeout_in_s = 0
        self.open_files = {}

    def wait_for_timeout(self):
        """
        Create a timeout that increase on recurrent failure
        """
        # continued calls to timeout shall increase wait time
        self.timeout_in_s += 5
        time.sleep(self.timeout_in_s)

    def reset_timeout(self):
        """
        Reset the length of the timeout after succesful reconnection
        """
        self.timeout_in_s = 0

    def get_data(
        self, access_token: str, timeout_in_s: int = 3500, output_dir: Path | str = None
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

        start_time = dt.datetime.now()
        with session.get(
            url=BARENTS_WATCH_LIVE_AIS_URL, headers=headers, stream=True,
            params={
                "modelType": "Full",
                "modelFormat": "Json",
            }
        ) as response:
            for idx, line in enumerate(response.iter_lines()):
                if line:
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
                            dt.datetime.now(dt.timezone.utc) - timestamp
                        ).total_seconds()
                        > 7200
                    ):
                        prev_day_filename = sorted(self.open_files.keys())[0]
                        self.open_files[prev_day_filename].close()
                        del self.open_files[prev_day_filename]


                    if path not in self.open_files or self.open_files[path][0].closed:
                        write_header = not path.exists()
                        fp = open(path, "a", newline="")
                        writer = csv.DictWriter(fp, fieldnames=list(data.keys()), quoting=csv.QUOTE_MINIMAL)
                        self.open_files[path] = (fp, writer)
                        if write_header:
                            writer.writeheader()

                    fp, writer = self.open_files[path]
                    writer.writerow(data)
                    fp.flush()

                    delta_time = (dt.datetime.now() - start_time).total_seconds()
                    print(
                        f"Processed {idx} message - current day: {day} -- (token used since: {int(delta_time)} s, renewal after: {self.timeout_in_s} s)",
                        end="\r",
                        flush=True,
                    )
                    if delta_time >= self.timeout_in_s:
                        raise RuntimeError(
                            f"Consumer.get_data: timeout after {self.timeout_in_s} seconds"
                        )

    def start(self, output_dir: Path | str = None):
        access = Access()
        while True:
            try:
                access.acquire()
                self.get_data(
                    access.access_token, access.expires_in, output_dir=output_dir
                )
                self.reset_timeout()
            except RuntimeError as e:
                if "timeout after" in f"{e}":
                    pass
                else:
                    raise
            except Exception as e:
                logger.warning(f"Protocol Error: {e}")
                self.wait_for_timeout()
            finally:
                [fp.close() for _,(fp,_) in self.open_files.items()]
