import datetime
import inspect
import sys
from pathlib import Path

from loguru import logger
import warnings


import logging
class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists.
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

def configure_logging(LOGPATH:Path):
    logging.basicConfig(level=logging.INFO)
    warnings.simplefilter(action='ignore', category=FutureWarning)
    warnings.simplefilter(action='ignore', category=UserWarning)

    #logger.add(sys.stdout, colorize=True, format="<green>{time}</green> <level>{message}</level>")
    logger.add(sys.stderr, format="{time} {level} {message}", filter="my_module", level="INFO")
    logger.add(f"{LOGPATH}/acooeaz_{datetime.date.today()}.log", rotation="12:00")
    return logger