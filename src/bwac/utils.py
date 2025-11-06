import datetime as dt
import logging
import re

from bwac.core.constants import (
    BARENTS_WATCH_DATETIME_PATTERN
)

logger = logging.getLogger(__name__)

def read_timestamp(msg_time: str):
    # some milliseconds go beyond six digits, so filtering those out
    try:
        timestamp = dt.datetime.fromisoformat(msg_time)
    except Exception as e:
        logger.debug(e)
        m = re.match(r"(.*T[0-9]{2}:[0-9]{2}:[0-9]{2})(\.[0-9]*)?(\+[0-9]{2}:[0-9]{2})", msg_time)

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

    return timestamp


def timestamp_to_txt(t: dt.datetime):
    value = t.strftime(BARENTS_WATCH_DATETIME_PATTERN)
    return value[:-6] + "Z"


class DayIterator:
    @classmethod
    def get_intervals(cls, from_date: dt.datetime, to_date: dt.datetime):
        end_of_day = from_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        intervals = []
        while end_of_day <= to_date:
            intervals.append([from_date, end_of_day])

            from_date = end_of_day + dt.timedelta(microseconds=1)
            end_of_day = from_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        if end_of_day != to_date and from_date < to_date:
            intervals.append([from_date, to_date])

        return intervals

