"""Point d'entrée : `python -m msdbr` lance le lecteur (ou le setup si config absente)."""

import logging

from . import config
from .player import start
from .setup import run as run_setup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

cfg = config.load()
if not cfg.get("api_base_url") or not cfg.get("msdb_id"):
    run_setup()
    cfg = config.load()

if not cfg.get("api_base_url") or not cfg.get("msdb_id"):
    raise SystemExit("Configuration incomplète. Abandon.")

start()
