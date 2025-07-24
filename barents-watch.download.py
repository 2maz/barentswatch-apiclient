import requests
import pandas as pd
import json
import time
import os
import re
import datetime as dt
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# API endpoint
api_url = "https://live.ais.barentswatch.no/v1/combined"

if not 'BARENTS_WATCH_ACCESS_TOKEN' in os.environ:
    raise ValueError("Missing BARENTS_WATCH_ACCESS_TOKEN")

access_token = os.environ['BARENTS_WATCH_ACCESS_TOKEN']

session = requests.Session()
headers = {
    "Authorization": f"Bearer {access_token}"
}
# Example data: b{"courseOverGround":268,"latitude":66.004573,"longitude":8.029767,"name":"TRANSOCEAN ENCOURAGE","rateOfTurn":-3,"shipType":90,"speedOverGround":0,"trueHeading":225,"navigationalStatus":3,"mmsi":258627000,"msgtime":"2025-07-24T10:14:50+00:00"}'

open_files = {}
last_day = None

with session.get(url=api_url, headers=headers, stream=True) as response:
    for idx, line in enumerate(response.iter_lines()):
        if line:
            data = json.loads(line.decode("UTF-8"))

            msg_time = data['msgtime']
            # some milliseconds go beyond six digits, so filtering those out
            try:
                timestamp = dt.datetime.fromisoformat(msg_time)
            except Exception as e:
                logger.debug(e)
                m = re.match("(.*T[0-9]{2}:[0-9]{2}:[0-9]{2})(\.[0-9]*)?(\+[0-9]{2}:[0-9]{2})", msg_time)

                milliseconds = m.groups()[1]
                if milliseconds == None:
                    milliseconds = '000000'
                else:
                    # strip . at the beginning
                    milliseconds = milliseconds[1:]
                    if len(milliseconds) > 6:
                        milliseconds = milliseconds[:6]
                    else:
                        milliseconds = milliseconds + '0'*(6 - len(milliseconds))

                iso_format = ''.join(m.groups()[0] + "." + milliseconds + m.groups()[2])
                timestamp = dt.datetime.fromisoformat(iso_format)

            day = timestamp.strftime("%Y_%m_%d")
            filename = f"AIS_{day}.csv"

            # considering maximum 2h delay of filename
            if len(open_files) == 2 and (dt.datetime.now() - timestamp).total_seconds() > 7200:
                prev_day_filename = sorted(open_files.keys())[0]
                del open_files[prev_day_filename]

            if filename not in open_files:
                write_header = False
                if not Path(filename).exists():
                    write_header = True

                fp = open(filename, 'a')
                open_files[filename] = fp
                if write_header:
                    header = ','.join(data.keys())
                    fp.write(f"{header}\n")

            values = ','.join([str(x) for x in data.values()])
            open_files[filename].write(f"{values}\n")

            print(f"Processed {idx} message - current day: {day}", end="\r")
