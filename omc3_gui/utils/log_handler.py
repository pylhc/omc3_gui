import sys
import os
import logging
from logging import StreamHandler, FileHandler


def set_up_console_logger(logger):
    logger.setLevel(logging.DEBUG)

    console_handler = StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    logger.addHandler(console_handler)
    return logger


def add_file_handler(log_dir):
    logger = logging.getLogger("")
    log_file = os.path.join(log_dir, "log.txt")
    file_handler = FileHandler(log_file, mode="w")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(get_file_formatter())
    logger.addHandler(file_handler)
    logger.info("Set up debug log file in: " +
                os.path.abspath(log_file))


def get_file_formatter():
    formatter = logging.Formatter(
        "%(name)s %(asctime)s %(levelname)s %(message)s"
    )
    formatter.datefmt = '%Y-%m-%d %H:%M:%S'
    return formatter


def get_console_formatter():
    formatter = logging.Formatter(
        "%(asctime)s %(name)20s | %(levelname)s - %(message)s"
    )
    formatter.datefmt = '%H:%M:%S'
    return formatter


def init_logging(level: int = None):
    """ Set up a basic logger. """
    if level is None:
        level = logging.DEBUG if sys.flags.debug else logging.INFO

    logging.basicConfig(
        stream=sys.stdout,
        level=level,
        format=get_console_formatter()._fmt,
        datefmt=get_console_formatter().datefmt,
    )