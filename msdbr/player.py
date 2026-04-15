"""Boucle de lecture principale et pilotage du WebView — équivalent PlayerActivity/PlayerViewModel."""

import logging
import subprocess
import threading
import time

import webview

from . import config
from .api import ApiError, MsdbsClient
from .models import MsdbUrl

log = logging.getLogger(__name__)

SCROLL_START_DELAY_S = 2.0
SCROLL_EDGE_PAUSE_S = 2.0
SCROLL_TICK_MS = 10
INITIAL_RETRY_DELAY_S = 5.0
MAX_RETRY_DELAY_S = 60.0
PAGE_TRANSITION_MS = 500
NO_SIGNAL_MARKER = "no-signal.html"
NO_SIGNAL_DISPLAY_S = 10.0
NO_SIGNAL_POLL_S = 30.0
WAKE_DISPLAY_S = 10.0


def _scroll_script(speed_px: int, tempo_s: float, display_duration_s: int) -> str:
    """Injecté dans la page pour piloter l'auto-scroll et signaler la fin de cycle.

    Utilise requestAnimationFrame (cale sur le vsync) + déplacement
    proportionnel au temps écoulé pour un rendu fluide.
    """
    return f"""
    (function() {{
        window.__msdbrCycleDone = false;
        const SPEED_PX_PER_10MS = {speed_px};
        const PX_PER_MS = SPEED_PX_PER_10MS / 10;
        const TEMPO_MS = {int(tempo_s * 1000)};
        const DISPLAY_S = {display_duration_s};
        let paused = true;
        let lastTs = null;
        let scrollAcc = 0;

        const isAtEnd = () =>
            document.documentElement.scrollHeight <= window.innerHeight ||
            (window.scrollY + window.innerHeight) >= (document.documentElement.scrollHeight - 2);

        const pauseAtBottom = () => {{
            paused = true;
            setTimeout(() => {{
                if (DISPLAY_S <= 0) {{
                    window.__msdbrCycleDone = true;
                    return;
                }}
                window.scrollTo(0, 0);
                setTimeout(() => {{ paused = false; lastTs = null; requestAnimationFrame(frame); }}, TEMPO_MS);
            }}, TEMPO_MS);
        }};

        const frame = (ts) => {{
            if (paused) return;
            if (lastTs === null) lastTs = ts;
            const dt = ts - lastTs;
            lastTs = ts;
            if (isAtEnd()) {{ pauseAtBottom(); return; }}
            scrollAcc += PX_PER_MS * dt;
            if (scrollAcc >= 1) {{
                const step = Math.floor(scrollAcc);
                window.scrollBy(0, step);
                scrollAcc -= step;
            }}
            requestAnimationFrame(frame);
        }};

        setTimeout(() => {{
            if (isAtEnd()) {{ pauseAtBottom(); return; }}
            paused = false;
            requestAnimationFrame(frame);
        }}, TEMPO_MS);
    }})();
    """


class Player:
    def __init__(self, client: MsdbsClient, msdb_id: str):
        self.client = client
        self.msdb_id = msdb_id
        self.window: webview.Window | None = None
        self.loaded_url: str | None = None
        self._stop = threading.Event()
        self._page_loaded = threading.Event()
        self._on_no_signal = False

    def run(self) -> None:
        self.window = webview.create_window(
            "MSDBR", html=self._loading_html(), fullscreen=True
        )
        self.window.events.loaded += self._on_loaded
        webview.start(func=self._playback_thread, private_mode=False)

    def _on_loaded(self) -> None:
        self._page_loaded.set()

    def _playback_thread(self) -> None:
        retry_delay = INITIAL_RETRY_DELAY_S
        while not self._stop.is_set():
            try:
                url = self.client.get_next_url(self.msdb_id)
                retry_delay = INITIAL_RETRY_DELAY_S
                if NO_SIGNAL_MARKER in url.url:
                    self._handle_no_signal(url)
                else:
                    if self._on_no_signal:
                        self._wake_display()
                        self._on_no_signal = False
                    self._display(url)
                    self._wait_for_next(url)
            except ApiError as exc:
                log.warning("Erreur API: %s — retry dans %ss", exc, retry_delay)
                self._show_error(str(exc))
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY_S)

    def _handle_no_signal(self, url: MsdbUrl) -> None:
        """Affiche no-signal 10s puis éteint HDMI. Tant que le serveur renvoie
        no-signal, on reste en veille. Une touche clavier réveille l'écran via
        DPMS (géré par X) — on le rallume 10s puis on coupe de nouveau.
        """
        if not self._on_no_signal:
            log.info("Page no-signal — affichage %ss puis veille HDMI", NO_SIGNAL_DISPLAY_S)
            self._display(url)
            self._sleep_interruptible(NO_SIGNAL_DISPLAY_S)
            if self._stop.is_set():
                return
            self._sleep_display()
            self._on_no_signal = True
        else:
            if self._display_is_on():
                log.info("Écran réveillé par input — affichage %ss", WAKE_DISPLAY_S)
                self._sleep_interruptible(WAKE_DISPLAY_S)
                if not self._stop.is_set():
                    self._sleep_display()
            else:
                self._sleep_interruptible(NO_SIGNAL_POLL_S)

    @staticmethod
    def _sleep_display() -> None:
        try:
            subprocess.run(["xset", "dpms", "force", "off"], check=False, timeout=2)
        except Exception as exc:
            log.warning("Veille HDMI échouée: %s", exc)

    @staticmethod
    def _wake_display() -> None:
        try:
            subprocess.run(["xset", "dpms", "force", "on"], check=False, timeout=2)
        except Exception as exc:
            log.warning("Réveil HDMI échoué: %s", exc)

    @staticmethod
    def _display_is_on() -> bool:
        try:
            result = subprocess.run(
                ["xset", "q"], capture_output=True, text=True, timeout=2
            )
            return "Monitor is On" in result.stdout
        except Exception:
            return True

    def _display(self, url: MsdbUrl) -> None:
        if self.loaded_url != url.url:
            self.loaded_url = url.url
            self._page_loaded.clear()
            self.window.load_url(url.url)
            if not self._page_loaded.wait(timeout=15):
                log.warning("Timeout chargement page %s", url.url)
        else:
            self.window.evaluate_js("window.scrollTo(0, 0);")
        self.window.evaluate_js("window.__msdbrCycleDone = false;")
        tempo = url.tempo_scroll if url.tempo_scroll > 0 else SCROLL_EDGE_PAUSE_S
        self.window.evaluate_js(
            _scroll_script(url.scroll_speed, tempo, url.display_duration_seconds)
        )
        log.info(
            "Affichage %s (duration=%ss, tempo=%ss, speed=%s)",
            url.url, url.display_duration_seconds, tempo, url.scroll_speed,
        )

    def _wait_for_next(self, url: MsdbUrl) -> None:
        if url.display_duration_seconds > 0:
            self._sleep_interruptible(url.display_duration_seconds)
            return
        # durée = 0 : attendre que le JS ait posé __msdbrCycleDone
        deadline = time.time() + 300
        while time.time() < deadline and not self._stop.is_set():
            done = self.window.evaluate_js("window.__msdbrCycleDone === true")
            if done is True:
                log.info("Cycle scroll terminé, page suivante")
                return
            time.sleep(0.2)
        log.warning("Timeout cycle scroll (300s) — page suivante forcée")

    def _sleep_interruptible(self, seconds: float) -> None:
        self._stop.wait(seconds)

    def _show_error(self, message: str) -> None:
        if self.window is None:
            return
        html = f"""
        <html><body style='background:#000;color:#fff;font-family:sans-serif;
        display:flex;align-items:center;justify-content:center;height:100vh;text-align:center;'>
        <div><h1>Erreur de connexion</h1><p>{message}</p>
        <p>Nouvelle tentative en cours…</p></div></body></html>
        """
        self.window.load_html(html)
        self.loaded_url = None

    @staticmethod
    def _loading_html() -> str:
        return """
        <html><body style='background:#000;color:#fff;font-family:sans-serif;
        display:flex;align-items:center;justify-content:center;height:100vh;'>
        <h2>Connexion au serveur MSDBS…</h2></body></html>
        """


def start() -> None:
    cfg = config.load()
    base_url = cfg.get("api_base_url")
    msdb_id = cfg.get("msdb_id")
    if not base_url or not msdb_id:
        raise SystemExit(
            "Configuration manquante. Définir api_base_url et msdb_id dans ~/.config/msdbr/config.json"
        )
    Player(MsdbsClient(base_url), msdb_id).run()
