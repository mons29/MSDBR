# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

MSDB-RaspberryApp — port Python du client Android TV `MSDBA` (voir `../MSDBA/` côté Kotlin). Cible principale : **Raspberry Pi Zero 2W / Pi 4** sous Raspberry Pi OS Bookworm "with desktop". Affiche en plein écran les URLs planifiées renvoyées par le serveur **MSDBS** (`GET /api/scheduler/next?msdbId=<id>`), avec auto-scroll, dans une fenêtre WebView.

Le backend MSDBS n'est pas dans ce repo. Le contrat API est strictement identique à celui consommé par l'app Android :
- `GET /api/scheduler/next?msdbId=<id>` → `MsdbUrl { id, url, displayDurationSeconds, scrollSpeed, tempoScroll, rafraichissement }`
- (prévu côté Android, pas encore porté Linux) `GET /api/app/latest` → `{ versionCode, versionName, apkUrl }`

Chaque fois que le DTO `MsdbUrl` évolue côté serveur, mettre à jour **à la fois** `../MSDBA/app/src/main/java/com/msdb/msdba/data/model/MsdbUrl.kt` **et** `msdb_raspberryapp/models.py`.

## Environnement de dev

Développement recommandé : **VS Code + Remote-SSH sur le Pi**. Édition sur PC, exécution sur le Pi. L'interpréteur Python sélectionné doit être le venv créé sur le Pi (`/home/pi/MSDB-RaspberryApp/venv/bin/python`).

**Dépendances système** (à installer sur le Pi, pas via pip) :
```bash
sudo apt install -y python3-venv python3-pip \
    libwebkit2gtk-4.1-0 gir1.2-webkit2-4.1 \
    libgirepository1.0-dev gcc libcairo2-dev pkg-config \
    python3-gi python3-gi-cairo
```
Note : sur anciennes versions Raspberry Pi OS, WebKit2GTK peut être `4.0-37` au lieu de `4.1-0` — `pywebview` détecte automatiquement mais les paquets `apt` diffèrent.

## Commandes

```bash
# Setup (une fois)
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# Config (une fois)
mkdir -p ~/.config/msdb-raspberryapp
cat > ~/.config/msdb-raspberryapp/config.json <<EOF
{ "api_base_url": "http://192.168.1.100:5000", "msdb_id": "DEVICE_001" }
EOF

# Lancement manuel (nécessite DISPLAY — donc depuis une session desktop ou SSH avec X forwarding)
DISPLAY=:0 venv/bin/python -m msdb_raspberryapp

# Déploiement systemd
sudo cp systemd/msdb-raspberryapp.service /etc/systemd/system/
sudo systemctl enable --now msdb-raspberryapp
journalctl -u msdb-raspberryapp -f                    # logs live
sudo systemctl restart msdb-raspberryapp              # redémarrer après code change
```

Il n'y a pas de suite de tests ni de linter configuré. Exécution manuelle via `python -m msdb_raspberryapp` uniquement.

## Architecture

**Threading model critique** : `pywebview` démarre sa boucle GTK sur le thread principal via `webview.start(func=...)`. La fonction passée (`_playback_thread`) tourne dans un thread worker. **Toute interaction avec `self.window`** (`load_url`, `evaluate_js`, `load_html`) doit passer par le worker — pas de calls GTK directs hors de là.

**Auto-scroll = JS injecté** (`player._scroll_script`), pas de boucle Python pour scroller. La logique correspond à celle de `autoScrollRunnable` dans `PlayerActivity.kt` côté Android :
- Délai initial `tempoScroll` (s) avant de commencer à scroller.
- À chaque tick (10 ms), `window.scrollBy(0, scrollSpeed)`.
- Arrivé en bas → pause `tempoScroll` → remonte → pause `tempoScroll` → nouveau cycle.
- Si `displayDurationSeconds <= 0` : un seul cycle, positionne `window.__msdbRaspberryAppCycleDone = true`, le worker Python poll cette variable pour avancer à la page suivante (équivalent du `signalScrollCycleComplete()` Kotlin).

**Boucle de lecture** (`Player._playback_thread`) : fetch → display → wait → repeat. Sur erreur API, retry exponentiel 5s → 60s max (miroir de `PlayerViewModel.runPlaybackLoop`). Pendant l'attente, le WebView garde la page courante affichée (sauf sur le tout premier échec où on affiche une page d'erreur locale).

**Config** : un simple `~/.config/msdb-raspberryapp/config.json` via `config.py`. Pas d'UI de setup (contrairement à l'app Android qui a `SetupActivity`). Le fichier doit exister avant lancement — sinon `SystemExit`.

## État d'implémentation (vs app Android)

Porté :
- Fetch + affichage + boucle.
- Auto-scroll avec `scrollSpeed` et `tempoScroll`.
- `displayDurationSeconds == 0` → un cycle puis suivante.
- Page d'erreur locale (retry exponentiel).

**Pas encore porté** (par ordre de priorité utilisateur) :
1. Détection URL `no-signal.html` + mise en veille HDMI via `vcgencmd display_power 0`/`1`, réveil sur input clavier, veille après 10 s.
2. Page d'erreur HTTP 503 dédiée.
3. Rafraîchissement périodique (champ `rafraichissement` en secondes, 0 = jamais).
4. OTA auto-update (endpoint `/api/app/latest` + `apt`/`git pull` + `systemctl restart`).
5. Timeout de chargement de page (15 s) avec page "ne répond pas".

Tous ces comportements existent déjà côté Kotlin dans `../MSDBA/app/src/main/java/com/msdb/msdba/ui/player/PlayerActivity.kt` — c'est la référence fonctionnelle.

## Particularités Raspberry Pi

- **Veille HDMI** : Linux permet ce qu'Android TV interdit. `vcgencmd display_power 0` éteint la sortie HDMI, `1` la rallume. Utiliser via `subprocess.run(["vcgencmd", "display_power", "0"])`.
- **GPU acceleration** : ajouter `dtoverlay=vc4-kms-v3d` dans `/boot/firmware/config.txt` améliore nettement le rendu WebKit.
- **systemd units** : `After=graphical.target` + `Environment=DISPLAY=:0` indispensables sinon le WebView ne peut pas s'attacher à l'écran.
