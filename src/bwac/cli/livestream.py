from argparse import ArgumentParser
from pathlib import Path

from bwac.cli.base import BaseParser
from bwac.core.livestream_consumer import LivestreamConsumer

import logging

logger = logging.getLogger(__name__)

class LivestreamParser(BaseParser):
    def __init__(self, parser: ArgumentParser):
        super().__init__(parser=parser)

        parser.add_argument("--output-dir",
                type=str,
                default=str(Path()),
                help=f"Output directory to use"
        )

    def execute(self, args):
        super().execute(args)

        consumer = LivestreamConsumer()
        logger.info(f"Starting consumer with output directory: {args.output_dir}")
        consumer.start(output_dir=args.output_dir)
