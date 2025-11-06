from argparse import ArgumentParser
import sys
import logging
from logging import basicConfig, getLogger

from bwac.cli.base import BaseParser
from bwac.cli.livestream import LivestreamParser
from bwac.cli.historic import HistoricParser

from bwac import __version__
import traceback as tb

logger = getLogger(__name__)
logger.setLevel(logging.INFO)


class MainParser(ArgumentParser):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.description = "bwac - barentswatch apiclient"
        self.add_argument("--log-level", type=str, default="INFO", help="Logging level")
        self.add_argument("--version", "-i", action="store_true", help="Show version")
        self.add_argument("--verbose", action="store_true", help="Show details")

    def attach_subcommand_parser(
        self, subcommand: str, help: str, parser_klass: BaseParser
    ):
        if not hasattr(self, "subparsers"):
            # lazy initialization, since it cannot be part of the __init__ function
            # otherwise random errors
            self.subparsers = self.add_subparsers(help="sub-command help")

        subparser = self.subparsers.add_parser(subcommand)
        parser_klass(parser=subparser)


def run():
    basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    main_parser = MainParser()

    main_parser.attach_subcommand_parser(
        subcommand="live",
        help="Connect and use the livestream",
        parser_klass=LivestreamParser,
    )

    main_parser.attach_subcommand_parser(
        subcommand="historic",
        help="Connect and use the historic data interface",
        parser_klass=HistoricParser,
    )

    args = main_parser.parse_args()

    if args.version:
        print(__version__)
        sys.exit(0)

    if hasattr(args, "active_subparser"):
        try:
            getattr(args, "active_subparser").execute(args)
        except Exception as e:
            print(f"Error: {e}")
            if args.verbose:
                tb.print_tb(e.__traceback__)
            sys.exit(-1)
    else:
        main_parser.print_help()

    for logger in [logging.getLogger(x) for x in logging.root.manager.loggerDict]:
        logger.setLevel(logging.getLevelName(args.log_level))


if __name__ == "__main__":
    run()
