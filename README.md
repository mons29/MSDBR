# MSDBR (Raspberry Pi)

POC du client MSDBA porté sur Linux / Raspberry Pi (MSDBR = MSDB Raspberry). Même contrat API que la version Android — consomme `GET /api/scheduler/next` et affiche l'URL planifiée en plein écran avec auto-scroll.

## Statut

POC minimal. Fonctionnalités couvertes :
- Boucle fetch → affichage → délai → fetch suivante.
- Auto-scroll avec `scrollSpeed`, pause haut/bas via `tempoScroll`.
- Page de secours si l'API tombe, retry exponentiel.
- `displayDurationSeconds = 0` → scroll un cycle puis passe à la page suivante.

Non implémenté (à porter depuis l'app Android) :
- Détection no-signal.html + mise en veille HDMI (`vcgencmd display_power 0`).
- Page d'erreur HTTP 503.
- Rafraîchissement périodique (`rafraichissement`).
- OTA auto-update.

## Dépendances

- Raspberry Pi OS (testé cible : Bookworm Lite) + X11 minimal OU Wayland (labwc/cage).
- Python 3.11+.
- WebKit2GTK : `sudo apt install libwebkit2gtk-4.1-0 gir1.2-webkit2-4.1`.

## Installation

```bash
sudo mkdir -p /opt/msdbr && sudo chown $USER /opt/msdbr
git clone <repo> /opt/msdbr
cd /opt/msdbr
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

## Configuration

```bash
mkdir -p ~/.config/msdbr
cat > ~/.config/msdbr/config.json <<EOF
{
  "api_base_url": "http://192.168.1.100:5000",
  "msdb_id": "DEVICE_LOBBY_001"
}
EOF
```

## Lancement manuel

```bash
DISPLAY=:0 venv/bin/python -m msdbr
```

## Lancement au démarrage (systemd)

```bash
sudo cp systemd/msdbr.service /etc/systemd/system/
sudo systemctl enable --now msdbr
journalctl -u msdbr -f
```
