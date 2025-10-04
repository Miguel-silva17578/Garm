import json
import tkinter as tk
from tkinter import filedialog, messagebox

CONFIG_FILE = "config.json"

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)

def open_ui():
    cfg = load_config()

    root = tk.Tk()
    root.title("Garm Save Sync")

    # Pasta de destino
    def choose_backup():
        folder = filedialog.askdirectory()
        if folder:
            cfg["backup_dir"] = folder
            backup_var.set(folder)
            save_config(cfg)

    backup_var = tk.StringVar(value=cfg["backup_dir"])
    tk.Label(root, text="Pasta de backup:").pack()
    tk.Entry(root, textvariable=backup_var, width=50).pack()
    tk.Button(root, text="Escolher...", command=choose_backup).pack()

    # Pastas monitoradas
    listbox = tk.Listbox(root, width=60, height=8)
    for w in cfg["watch_dirs"]:
        listbox.insert(tk.END, w)
    listbox.pack()

    def add_folder():
        folder = filedialog.askdirectory()
        if folder:
            cfg["watch_dirs"].append(folder)
            listbox.insert(tk.END, folder)
            save_config(cfg)

    def remove_folder():
        sel = listbox.curselection()
        if sel:
            idx = sel[0]
            removed = cfg["watch_dirs"].pop(idx)
            listbox.delete(idx)
            save_config(cfg)
            messagebox.showinfo("Removido", f"Pasta removida: {removed}")

    tk.Button(root, text="Adicionar pasta", command=add_folder).pack()
    tk.Button(root, text="Remover pasta", command=remove_folder).pack()

    root.mainloop()
