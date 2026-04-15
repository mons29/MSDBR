# Historique de conversation — MSDBA / portage Linux (MSDBR)

Résumé chronologique de la session Claude Code ayant produit le projet. À lire avant de reprendre le travail pour comprendre le contexte et les décisions.

## 1. Travaux sur l'app Android (MSDBA, dossier voisin `../MSDBA/`)

Ordre chronologique des demandes traitées, avec le résultat final appliqué.

1. **"deploi" défini comme raccourci** : build APK debug + install + launch sur l'émulateur `Television_1080p` uniquement (emulator-5554). Sauvegardé en mémoire persistante Android.
2. **Pause de scroll** : la pause existante en bas de page (`SCROLL_EDGE_PAUSE_MS = 2000L`) est maintenant aussi appliquée en haut de page (au démarrage et après chaque retour en haut).
3. **Champs backend ajoutés à `MsdbUrl`** :
   - `tempoScroll` (s) : remplace `SCROLL_START_DELAY_MS` et `SCROLL_EDGE_PAUSE_MS` **si > 0** (sinon valeurs par défaut 2s).
   - `rafraichissement` (s) : reload périodique de la page après chaque `onPageFinished`. `0` = jamais.
4. **Page d'erreur "ne répond pas"** : timeout de chargement 15 s + gestion `onReceivedError` main frame → affichage `status_page_unresponsive` + retry après 5 s.
5. **Erreurs HTTP (503, etc.)** : `onReceivedHttpError` main frame → page d'erreur avec code et raison (`status_page_http_error`), même mécanique de retry.
6. **`displayDurationSeconds == 0`** : la page s'affiche normalement, scroll un cycle complet (startDelay → scroll → edgePause), puis `PlayerActivity.viewModel.signalScrollCycleComplete()` débloque le VM via `CompletableDeferred`. Les pages plus courtes que le viewport signalent également fin de cycle.
7. **Mode `no-signal.html`** : si l'URL reçue contient `no-signal.html` → affichée 10 s, puis overlay noir plein écran + retrait de `FLAG_KEEP_SCREEN_ON`. Une touche réveille la page 10 s. Dès qu'une autre URL arrive, veille annulée.
8. **Publication Play Store** : ajout banner TV vectoriel (`tv_banner.xml`, placeholder), icon vectoriel, `network_security_config.xml` remplaçant `usesCleartextTraffic`, signing config release via `keystore.properties` (sample fourni, `.gitignore` créé). `targetSdk` passé à 35.
9. **OTA auto-update (sans Play Store)** :
   - `AppUpdate { versionCode, versionName, apkUrl }`.
   - `ApiService.getLatestAppVersion()` + `downloadApk(@Url)`.
   - `UpdateManager` : compare à `BuildConfig.VERSION_CODE`, télécharge dans `cacheDir`, lance `ACTION_VIEW` via FileProvider.
   - Permission `REQUEST_INSTALL_PACKAGES` + FileProvider + `res/xml/file_paths.xml`.
   - Appelé au démarrage de `PlayerActivity`.
   - Côté serveur MSDBS : endpoint `GET /api/app/latest` à implémenter. APK doit être signé avec **le même keystore** que la version installée.

## 2. Décision de portage Raspberry Pi

- L'utilisateur a demandé un portage du client sur Raspberry Pi Linux.
- Cible matérielle confirmée : **Raspberry Pi 2 Model B** (ARMv7 32-bit, 1 Go RAM). Viable pour tester, un peu limite sur du web lourd.
- OS recommandé : **Raspberry Pi OS Bookworm "with desktop" (32-bit)**.
- Environnement de dev : **VS Code + Remote-SSH sur le Pi** (interpréteur Python = venv sur le Pi). L'utilisateur va reprendre depuis VS Code — d'où ce fichier.

## 3. Contenu du POC Linux créé (ce dossier)

Voir `CLAUDE.md` et `README.md` pour les détails techniques à jour.

**Ce qui est porté** :
- Fetch `GET /api/scheduler/next` + boucle d'affichage + retry exponentiel.
- Auto-scroll via JS injecté dans la page (miroir du runnable Kotlin).
- `tempoScroll` appliqué si > 0.
- `displayDurationSeconds == 0` → un cycle, signal via `window.__msdbrCycleDone`.
- Page d'erreur locale sur échec API.
- Config persistée dans `~/.config/msdbr/config.json` (pas d'UI Setup pour l'instant).
- Unit systemd prête (`systemd/msdbr.service`).

**Backlog non porté** (par ordre de priorité utilisateur) :
1. No-signal + veille HDMI (`vcgencmd display_power 0/1`) + réveil sur touche.
2. Page 503 dédiée.
3. Rafraîchissement périodique (champ `rafraichissement`).
4. OTA auto-update (endpoint `/api/app/latest`, `apt`/`git pull` + `systemctl restart`).
5. Timeout de chargement page (15 s).

## 4. Points techniques à ne pas oublier

- **Contrat API partagé** : toute évolution du DTO doit être répercutée dans les deux modèles (`../MSDBA/.../data/model/MsdbUrl.kt` **et** `msdbr/models.py`).
- **Threading pywebview** : `webview.start(func=...)` démarre GTK sur le main thread, `func` tourne dans un worker. Tout accès à `self.window` doit se faire depuis ce worker.
- **Endpoint `/api/app/latest` attendu** (même contrat des deux côtés quand porté) :
  ```json
  { "versionCode": 2, "versionName": "1.1.0", "apkUrl": "http://.../msdba-1.1.0.apk" }
  ```
  Pour Linux on remplacera probablement `apkUrl` par un tarball ou `pip`/`git` — à discuter.

## 5. Préférences utilisateur notées pendant la session

- Préfère qu'on aille à l'essentiel, pas de résumés trop longs.
- Cible hardware : Pi 2 Model B pour les tests, Pi Zero 2W envisagé en production.
- Développement : Windows 11 + VS Code. Auparavant : Android Studio pour la version Kotlin.

## 6. Prochaine étape suggérée

1. Flasher Raspberry Pi OS Bookworm (with desktop, 32-bit) via Pi Imager.
2. SSH activé, copier le projet sur le Pi.
3. Suivre le `README.md` pour installer les deps système + venv.
4. Premier run manuel : `DISPLAY=:0 venv/bin/python -m msdbr`.
5. Si OK, activer le service systemd.
6. Implémenter en priorité le point 1 du backlog (no-signal + veille HDMI) — c'est là que Linux est plus capable qu'Android TV.
