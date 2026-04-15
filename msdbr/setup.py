"""Fenêtre de configuration MSDBR (équivalent SetupActivity côté Android)."""

import tkinter as tk
from tkinter import ttk, messagebox

from . import config


def _build_ui(root: tk.Tk) -> None:
    cfg = config.load()
    root.title("MSDBR — Configuration")
    root.geometry("480x260")
    root.resizable(False, False)

    frame = ttk.Frame(root, padding=20)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text="URL serveur MSDBS").grid(row=0, column=0, sticky="w", pady=4)
    url_var = tk.StringVar(value=cfg.get("api_base_url", ""))
    ttk.Entry(frame, textvariable=url_var, width=40).grid(row=0, column=1, pady=4)

    ttk.Label(frame, text="ID de l'écran").grid(row=1, column=0, sticky="w", pady=4)
    id_var = tk.StringVar(value=cfg.get("msdb_id", ""))
    ttk.Entry(frame, textvariable=id_var, width=40).grid(row=1, column=1, pady=4)

    sleep_var = tk.BooleanVar(value=cfg.get("enable_sleep", True))
    ttk.Checkbutton(
        frame, text="Activer la veille HDMI sur no-signal", variable=sleep_var
    ).grid(row=2, column=0, columnspan=2, sticky="w", pady=8)

    status = ttk.Label(frame, text="", foreground="green")
    status.grid(row=3, column=0, columnspan=2, pady=4)

    def on_save() -> None:
        url = url_var.get().strip().rstrip("/")
        msdb_id = id_var.get().strip()
        if not url or not msdb_id:
            messagebox.showerror("Erreur", "URL et ID sont obligatoires.")
            return
        config.save({
            "api_base_url": url,
            "msdb_id": msdb_id,
            "enable_sleep": bool(sleep_var.get()),
        })
        status.config(text="Configuration enregistrée. Redémarrez MSDBR pour appliquer.")

    btns = ttk.Frame(frame)
    btns.grid(row=4, column=0, columnspan=2, pady=12)
    ttk.Button(btns, text="Enregistrer", command=on_save).pack(side="left", padx=6)
    ttk.Button(btns, text="Fermer", command=root.destroy).pack(side="left", padx=6)


def run() -> None:
    root = tk.Tk()
    _build_ui(root)
    root.mainloop()


if __name__ == "__main__":
    run()
