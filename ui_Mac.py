# ui_Mac.py
import json
import customtkinter as ctk
from tkinter import filedialog, messagebox
from threading import Thread, Event
from sync import start_sync, stop_sync
import sys
from pathlib import Path
import tkinter as tk
import ctypes  # necessário para AppUserModelID no Windows

# ---- Config / globals ----
CONFIG_FILE = "config.json"
sync_thread = None
stop_event = Event()

# AppUserModelID (mude se quiser)
MY_APPID = u"com.garm.garmsavesync"

def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"watch_dirs": [], "backup_dir": ""}

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)

def open_ui():
    """
    Inicializa a UI. Coloquei a chamada para SetCurrentProcessExplicitAppUserModelID
    antes da criação da janela (necessário no Windows para que o ícone da taskbar seja aplicado).
    """
    global sync_thread

    # --- Windows: setar AppUserModelID o quanto antes (antes de criar janelas) ---
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(MY_APPID)
        except Exception as e:
            # não falha a app por causa disso; apenas loga
            print("Não foi possível setar AppUserModelID:", e)

    cfg = load_config()

    # ---- Tema e janela ----
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()

    # ---- ICON: tentativa de carregar garm.ico (Windows) ou PNG (fallback) ----
    # base_path lida com execução empacotada (PyInstaller)
    if getattr(sys, "frozen", False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent

    icon_ico = base_path / "garm.ico"
    icon_png = base_path / "garm-256.png"  # recomenda-se ter este PNG como fallback

    try:
        if sys.platform.startswith("win") and icon_ico.exists():
            # Windows: preferir .ico
            try:
                root.iconbitmap(str(icon_ico))
            except Exception as e:
                # fallback para PNG via PhotoImage
                print("iconbitmap falhou:", e)
                if icon_png.exists():
                    try:
                        img = tk.PhotoImage(file=str(icon_png))
                        root.iconphoto(False, img)
                        root._icon_img = img  # manter referência
                    except Exception:
                        pass
        else:
            # non-Windows: tentar usar PNG
            if icon_png.exists():
                try:
                    img = tk.PhotoImage(file=str(icon_png))
                    root.iconphoto(False, img)
                    root._icon_img = img
                except Exception:
                    pass
            elif icon_ico.exists():
                # algumas builds do Tk aceitam .ico via PhotoImage (tentar)
                try:
                    img = tk.PhotoImage(file=str(icon_ico))
                    root.iconphoto(False, img)
                    root._icon_img = img
                except Exception:
                    pass
    except Exception:
        # não deixar erro de ícone quebrar a UI
        pass
    # ---- fim do bloco de ícone ----

    root.title("Garm Save Sync")
    root.geometry("500x500")

    title = ctk.CTkLabel(root, text="Garm Save Sync", font=("SF Pro Display", 22, "bold"))
    title.pack(pady=(20, 10))

    # ---- Pasta de backup ----
    frame_backup = ctk.CTkFrame(root, corner_radius=10)
    frame_backup.pack(fill="x", padx=20, pady=10)

    ctk.CTkLabel(frame_backup, text="📂 Pasta de backup:").pack(anchor="w", padx=10, pady=5)
    backup_var = ctk.StringVar(value=cfg.get("backup_dir", ""))
    entry = ctk.CTkEntry(frame_backup, textvariable=backup_var, width=350)
    entry.pack(side="left", padx=(10, 5), pady=10)

    def choose_backup():
        folder = filedialog.askdirectory()
        if folder:
            cfg["backup_dir"] = folder
            backup_var.set(folder)
            save_config(cfg)

    ctk.CTkButton(frame_backup, text="Escolher", command=choose_backup).pack(side="left", padx=5, pady=10)

    # ---- Pastas monitoradas ----
    frame_list = ctk.CTkFrame(root, corner_radius=10)
    frame_list.pack(fill="both", expand=True, padx=20, pady=10)

    ctk.CTkLabel(frame_list, text="📁 Pastas monitoradas:").pack(anchor="w", padx=10, pady=5)

    listbox = ctk.CTkTextbox(frame_list, width=450, height=150)
    listbox.pack(padx=10, pady=5)
    listbox.configure(state="disabled")

    def refresh_listbox():
        listbox.configure(state="normal")
        listbox.delete("1.0", "end")
        for w in cfg.get("watch_dirs", []):
            listbox.insert("end", w + "\n")
        listbox.configure(state="disabled")

    refresh_listbox()

    def add_folder():
        folder = filedialog.askdirectory()
        if folder:
            cfg.setdefault("watch_dirs", []).append(folder)
            save_config(cfg)
            refresh_listbox()

    def remove_folder():
        content = listbox.get("1.0", "end").strip().split("\n")
        content = [c for c in content if c.strip() != ""]
        if not content:
            return
        folder = content[-1]  # manter comportamento: remove a última
        if folder in cfg.get("watch_dirs", []):
            cfg["watch_dirs"].remove(folder)
            save_config(cfg)
            refresh_listbox()
            messagebox.showinfo("Removido", f"Pasta removida: {folder}")

    # ---- Linha de botões: Adicionar / Remover / Iniciar (toggle) ----
    btn_frame = ctk.CTkFrame(root, fg_color="transparent")
    btn_frame.pack(pady=5)

    ctk.CTkButton(btn_frame, text="Adicionar pasta", command=add_folder, width=140).pack(side="left", padx=6)
    ctk.CTkButton(btn_frame, text="Remover última", command=remove_folder, width=140).pack(side="left", padx=6)

    # ---- Indicador de status ----
    status_frame = ctk.CTkFrame(root, corner_radius=10)
    status_frame.pack(padx=20, pady=(10, 0), fill="x")

    status_label = ctk.CTkLabel(status_frame, text="Status: Parado", font=("SF Pro", 14))
    status_label.pack(side="left", padx=10, pady=10)

    indicator = ctk.CTkLabel(status_frame, text="●", font=("Arial", 18), text_color="gray")
    indicator.pack(side="right", padx=15)

    # ---- Controle de sincronização (toggle) ----
    syncing = False  # estado local da UI

    def set_running_state(running: bool):
        nonlocal syncing
        syncing = running
        if running:
            start_stop_btn.configure(text="⏹ Parar", fg_color="#e74c3c", hover_color="#c0392b")
            status_label.configure(text="Status: Sincronizando")
            indicator.configure(text_color="lime")
        else:
            start_stop_btn.configure(text="▶ Iniciar", fg_color="#2ecc71", hover_color="#27ae60")
            status_label.configure(text="Status: Parado")
            indicator.configure(text_color="gray")

    def start_sync_thread():
        global sync_thread
        stop_event.clear()
        sync_thread = Thread(target=start_sync, args=(cfg,), daemon=True)
        sync_thread.start()

    def toggle_sync():
        global sync_thread
        nonlocal syncing
        if not syncing:
            # iniciar
            if not cfg.get("backup_dir"):
                messagebox.showerror("Erro", "Escolha a pasta de backup primeiro!")
                return
            if not cfg.get("watch_dirs"):
                messagebox.showerror("Erro", "Adicione pelo menos uma pasta de saves!")
                return
            if sync_thread and sync_thread.is_alive():
                messagebox.showinfo("Já em execução", "A sincronização já está rodando!")
                set_running_state(True)
                return
            start_sync_thread()
            set_running_state(True)
            messagebox.showinfo("Iniciado", "Primeira cópia dos arquivos será feita agora e a sincronização em tempo real vai iniciar!")
        else:
            # parar
            stop_event.set()
            stop_sync()
            set_running_state(False)
            messagebox.showinfo("Parado", "Sincronização encerrada!")

    # botão Start/Stop (mesma linha)
    start_stop_btn = ctk.CTkButton(
        btn_frame,
        text="▶ Iniciar",
        command=toggle_sync,
        width=120,
        fg_color="#2ecc71",
        hover_color="#27ae60",
        font=("SF Pro Display", 14, "bold")
    )
    start_stop_btn.pack(side="left", padx=6)

    root.mainloop()

# Executa a UI diretamente
if __name__ == "__main__":
    open_ui()
