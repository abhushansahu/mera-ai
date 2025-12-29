import logging
import sys
from typing import Any, Dict, Optional

from pythonjsonlogger import jsonlogger


def setup_logging(level: str = "INFO") -> None:
    log_handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    log_handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    root_logger.addHandler(log_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
