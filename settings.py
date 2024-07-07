import os
from pathlib import Path
BASEPATH = Path(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
try:
    HOST = os.environ['SRV_HOST']
    if HOST == "dev":
        dotenv_path = Path(os.path.join(BASEPATH, "dev.env"))

    elif HOST == "prod":
        dotenv_path = Path(os.path.join(BASEPATH, "prod.env"))
    else:
        raise RuntimeError("Host env not specified")
except:
    dotenv_path = Path(os.path.join(BASEPATH, "local.env"))

load_dotenv(dotenv_path=dotenv_path, override=True)

from helpers.configure_logging import configure_logging
LOGPATH = Path.joinpath(BASEPATH, os.environ.get("LOGPATH", None))
logger = configure_logging(LOGPATH)
logger.info(f'loglevel: {os.environ.get("LOGURU_LEVEL", "DEBUG")}')

OEAZ_REST = os.environ.get("OEAZ_API", None)
MONGO_ENDPOINT= os.environ.get("MONGO_ENDPOINT", None)
MARKER_ENDPOINT= os.environ.get("MARKER_ENDPOINT", None)
OEAZ_ONLINE_STAGING_API = os.environ.get("OEAZ_ONLINE_STAGING_API", None)
OEAZ_ONLINE_API = os.environ.get("OEAZ_ONLINE_API", None)
ACO_API = os.environ.get('ACO_API', None)
ELASTIC = os.environ.get('ELASTIC', None)
# todo: put models to a volume
# todo: models loaded will always pull huggingface - should be local
#os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HOME"] = str(BASEPATH.joinpath("assets", "models").absolute())


IGNORE_SECTIONS = [
    "Kurz & Aktuell",
    "Mitteilungen",
    "Wichtiges in Kürze",
    "Mitteilungen Termine Impressum",
    "Chronik"
]
