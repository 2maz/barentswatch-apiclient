import requests
import pandas as pd
import json
import time
import os
import re
import datetime as dt
from pathlib import Path
import json

import logging

logger = logging.getLogger(__name__)


# API endpoint
api_url = "https://live.ais.barentswatch.no/v1/combined"

if not 'BARENTS_WATCH_ACCESS_TOKEN' in os.environ:
    raise ValueError("Missing BARENTS_WATCH_ACCESS_TOKEN")

access_token = os.environ['BARENTS_WATCH_ACCESS_TOKEN']

# Example data: b{"courseOverGround":268,"latitude":66.004573,"longitude":8.029767,"name":"TRANSOCEAN ENCOURAGE","rateOfTurn":-3,"shipType":90,"speedOverGround":0,"trueHeading":225,"navigationalStatus":3,"mmsi":258627000,"msgtime":"2025-07-24T10:14:50+00:00"}'

open_files = {}
last_day = None

timeout_in_s = 0

def wait_for_timeout():
    global timeout_in_s

    # continued calls to timeout shall increase wait time
    timeout_in_s += 5
    time.sleep(timeout_in_s)

def reset_timeout():
    global timeout_in_s

    timeout_in_s = 0

def acquire_token():
    if not 'BARENTS_WATCH_CLIENT_ID' in os.environ:
        raise ValueError("Missing BARENTS_WATCH_CLIENT_ID in env")
    if not 'BARENTS_WATCH_CLIENT_SECRET' in os.environ:
        raise ValueError("Missing BARENTS_WATCH_CLIENT_SECRET in env")

    client_id = os.environ["BARENTS_WATCH_CLIENT_ID"]
    client_secret = os.environ["BARENTS_WATCH_CLIENT_SECRET"]
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': 'ais',
        'grant_type': 'client_credentials'
    }

    response = requests.post("https://id.barentswatch.no/connect/token",
            headers=headers,
            data=data)
    return response.json()

def get_data(access_token: str, timeout_in_s: int = 3500):
    session = requests.Session()
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    start_time = dt.datetime.now()

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

                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=dt.timezone.utc)

                # considering maximum 2h delay of filename
                if len(open_files) == 2 and (dt.datetime.now(dt.timezone.utc) - timestamp).total_seconds() > 7200:
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

                delta_time = (dt.datetime.now() - start_time).total_seconds()
                print(f"Processed {idx} message - current day: {day} -- (token used since: {int(delta_time)} s, renewal after: {timeout_in_s} s)", end="\r")
                if  delta_time >= timeout_in_s:
                    raise RuntimeError(f"Timeout after {timeout_in_s} seconds") 

while True:
    try:
        token = acquire_token()
        get_data(token['access_token'], int(token['expires_in']))
        reset_timeout()
    except RuntimeError as e:
        if "Timeout" in f"{e}":
            pass
        else:
            raise
    except Exception as e:
        logger.warning(f"Protocol Error: {e}")
        wait_for_timeout()
