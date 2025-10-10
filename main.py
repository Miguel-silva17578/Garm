import threading
import tkinter as tk
from tkinter import filedialog, messagebox, Listbox
import json
from sync import start_sync, stop_sync

CONFIG_FILE = "config.json"

def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"watch_dirs": [], "backup_dir": "", "log_file": "sync_log.txt"}

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)

def run_ui():
    cfg = load_config()
    root = tk.Tk()
    root.title("Garm Save Sync")

    # --- Pasta de destino ---
    backup_var = tk.StringVar(value=cfg.get("backup_dir", ""))

    def choose_backup():
        folder = filedialog.askdirectory()
        if folder:
            backup_var.set(folder)
            cfg["backup_dir"] = folder
            save_config(cfg)

    tk.Label(root, text="📂 Pasta de Backup:").pack(pady=5)
    tk.Entry(root, textvariable=backup_var, width=50).pack()
    tk.Button(root, text="Escolher...", command=choose_backup).pack()

    # --- Pastas monitoradas ---
    tk.Label(root, text="🎮 Pastas de Saves Monitoradas:").pack(pady=5)
    listbox = Listbox(root, width=60, height=8)
    listbox.pack()

    for w in cfg["watch_dirs"]:
        listbox.insert(tk.END, w)

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

    # --- Controle do Sync ---
    sync_thread = None

    def start_button():
        nonlocal sync_thread
        if not cfg["backup_dir"]:
            messagebox.showerror("Erro", "Escolha a pasta de backup primeiro!")
            return
        if not cfg["watch_dirs"]:
            messagebox.showerror("Erro", "Adicione pelo menos uma pasta de saves!")
            return
        if sync_thread and sync_thread.is_alive():
            messagebox.showinfo("Já em execução", "A sincronização já está rodando!")
            return
        sync_thread = threading.Thread(target=start_sync, args=(cfg,), daemon=True)
        sync_thread.start()
        messagebox.showinfo("Iniciado", "Primeira cópia dos arquivos será feita agora e a sincronização em tempo real vai iniciar!")


    def stop_button():
        stop_sync()
        messagebox.showinfo("Parado", "Sincronização encerrada!")

    tk.Button(root, text="▶ Iniciar Sincronização", command=start_button, bg="green", fg="white").pack(pady=5)
    tk.Button(root, text="⏹ Parar Sincronização", command=stop_button, bg="red", fg="white").pack(pady=5)

    root.mainloop()

from ui_Mac import open_ui

if __name__ == "__main__":
    open_ui()


