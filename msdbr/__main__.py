"""Point d'entrée : `python -m msdbr` lance le lecteur."""

import logging

from .player import start

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
start()
