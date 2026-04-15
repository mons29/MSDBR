"""Auto-update MSDBR piloté par MSDBS (endpoint /api/app/latest-linux).

Compare la version locale (fichier VERSION à la racine du repo) à la version
distante renvoyée par MSDBS. Si différente : `git pull`, `pip install`, puis
redémarre openbox (qui relance MSDBR via son autostart).
"""

import logging
import subprocess
import threading
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_ROOT / "VERSION"
VENV_PIP = REPO_ROOT / "venv" / "bin" / "pip"


def local_version() -> str:
    try:
        return VERSION_FILE.read_text().strip()
    except OSError:
        return "0.0.0"


def fetch_remote_version(base_url: str, timeout: float = 10.0) -> str | None:
    try:
        r = requests.get(f"{base_url.rstrip('/')}/api/app/latest-linux", timeout=timeout)
        r.raise_for_status()
        return r.json().get("version")
    except (requests.RequestException, ValueError) as exc:
        log.warning("Check MAJ échoué: %s", exc)
        return None


def apply_update() -> None:
    log.info("Application MAJ : git pull + pip install")
    subprocess.run(["git", "-C", str(REPO_ROOT), "pull", "--ff-only"], check=True)
    subprocess.run(
        [str(VENV_PIP), "install", "-r", str(REPO_ROOT / "requirements.txt")],
        check=True,
    )
    log.info("MAJ installée, redémarrage via openbox --restart")
    subprocess.run(["openbox", "--restart"], check=False)


def check_and_update(base_url: str) -> None:
    remote = fetch_remote_version(base_url)
    if remote is None:
        return
    local = local_version()
    if remote != local:
        log.info("Nouvelle version disponible : locale=%s, distante=%s", local, remote)
        try:
            apply_update()
        except subprocess.CalledProcessError as exc:
            log.error("MAJ échouée: %s", exc)
    else:
        log.debug("À jour (%s)", local)


def start_update_loop(base_url: str, interval_s: int) -> None:
    def loop() -> None:
        time.sleep(5)
        while True:
            try:
                check_and_update(base_url)
            except Exception:
                log.exception("Erreur check MAJ")
            time.sleep(max(interval_s, 30))

    threading.Thread(target=loop, daemon=True, name="msdbr-updater").start()
    log.info("Auto-update activé (intervalle %ss)", interval_s)
