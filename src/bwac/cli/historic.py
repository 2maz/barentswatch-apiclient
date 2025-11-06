from pathlib import Path
from argparse import ArgumentParser
import datetime as dt
from tqdm import tqdm

from bwac.cli.base import BaseParser
from bwac.core.historic_consumer import HistoricConsumer
from bwac.utils import DayIterator


class HistoricParser(BaseParser):
    def __init__(self, parser: ArgumentParser):
        super().__init__(parser=parser)

        end_date = dt.datetime.now(tz=dt.timezone.utc)
        end_date_txt = end_date.isoformat()

        start_date = end_date - dt.timedelta(days=1)
        start_date_txt = start_date.isoformat()

        parser.add_argument(
            "--from-date",
            type=str,
            default=start_date_txt,
            help=f"From time (default: {start_date_txt})",
        )
        parser.add_argument(
            "--to-date",
            type=str,
            default=end_date_txt,
            help=f"To time (default: {end_date_txt})",
        )

        parser.add_argument(
            "--output-dir", type=str, default=str(Path()), help="The output directory"
        )

    def execute(self, args):
        super().execute(args)

        consumer = HistoricConsumer()
        from_date = dt.datetime.fromisoformat(args.from_date)
        to_date = dt.datetime.fromisoformat(args.to_date)

        for interval in DayIterator.get_intervals(from_date, to_date):
            from_date, to_date = interval

            mmsis = consumer.query_all_mmsis(from_date, to_date)
            for mmsi in tqdm(mmsis):
                track = consumer.query_track(
                    mmsi=mmsi, from_date=from_date, to_date=to_date
                )
                consumer.save_track(track, args.output_dir)
