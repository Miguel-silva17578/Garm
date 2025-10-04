import os
import shutil
import logging
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from threading import Thread, Event
from queue import Queue, Empty

# Lista global de observadores para parar depois
observers = []

# Fila de eventos de arquivos a serem sincronizados
file_queue = Queue()
stop_event = Event()

# Controle de debounce
last_event_time = {}
DEBOUNCE_DELAY = 2  # segundos sem mudanças para copiar

def sync_file(src_file, cfg):
    """Sincroniza arquivo modificado/adicionado"""
    try:
        src_file = Path(src_file)
        for base in cfg["watch_dirs"]:
            base_path = Path(base)
            if src_file.is_relative_to(base_path):
                rel_path = src_file.relative_to(base_path)
                dest_file = Path(cfg["backup_dir"]) / base_path.name / rel_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dest_file)
                logging.info(f"Atualizado: {dest_file}")
                print(f"[SYNC] {dest_file}")
                break
    except Exception as e:
        logging.error(f"Erro ao sincronizar {src_file}: {e}")

def initial_sync(cfg):
    """Faz a cópia inicial de todos os arquivos das pastas monitoradas"""
    for base in cfg["watch_dirs"]:
        base_path = Path(base)
        dest_base = Path(cfg["backup_dir"]) / base_path.name
        for root, dirs, files in os.walk(base_path):
            rel_path = Path(root).relative_to(base_path)
            dest_root = dest_base / rel_path
            dest_root.mkdir(parents=True, exist_ok=True)
            for file in files:
                src_file = Path(root) / file
                dest_file = dest_root / file
                if (not dest_file.exists() or
                    os.path.getmtime(src_file) > os.path.getmtime(dest_file)):
                    shutil.copy2(src_file, dest_file)
                    logging.info(f"Inicialmente copiado: {dest_file}")
                    print(f"[INIT] {dest_file}")

class SyncHandler(FileSystemEventHandler):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg

    def on_modified(self, event):
        if not event.is_directory:
            file_queue.put(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            file_queue.put(event.src_path)

    def on_deleted(self, event):
        # Ignorar exclusões para manter o backup seguro
        logging.info(f"Ignorado delete: {event.src_path}")
        print(f"[IGNORE DELETE] {event.src_path}")

def worker(cfg):
    """Thread que processa a fila de arquivos com debounce"""
    while not stop_event.is_set():
        try:
            src_file = file_queue.get(timeout=1)
            now = time.time()
            last_event_time[src_file] = now

            # Espera até que não haja novos eventos recentes para este arquivo
            while True:
                time.sleep(0.5)
                if stop_event.is_set():
                    break
                # Se não houve eventos novos nos últimos DEBOUNCE_DELAY segundos
                if time.time() - last_event_time[src_file] >= DEBOUNCE_DELAY:
                    break

            sync_file(src_file, cfg)
            file_queue.task_done()
        except Empty:
            continue

def start_sync(cfg):
    logging.basicConfig(filename=cfg.get("log_file", "sync_log.txt"), 
                        level=logging.INFO, format="%(asctime)s - %(message)s")

    # --- FAZ PRIMEIRA CÓPIA ---
    print("[INIT] Fazendo cópia inicial de todos os arquivos...")
    initial_sync(cfg)
    print("[INIT] Cópia inicial concluída!")

    # --- INICIA THREAD DE SINCRONIZAÇÃO ---
    t = Thread(target=worker, args=(cfg,), daemon=True)
    t.start()

    # --- INICIA MONITORAMENTO ---
    for folder in cfg["watch_dirs"]:
        observer = Observer()
        event_handler = SyncHandler(cfg)
        observer.schedule(event_handler, folder, recursive=True)
        observer.start()
        observers.append(observer)
        print(f"[MONITORANDO] {folder}")

    try:
        while True:
            time.sleep(1)  # mantém o loop vivo sem usar 100% da CPU
    except KeyboardInterrupt:
        stop_sync()

def stop_sync():
    stop_event.set()
    for obs in observers:
        obs.stop()
    for obs in observers:
        obs.join()
    observers.clear()
    print("[SYNC] Observadores parados")
    logging.info("Sincronização parada.")
    print("[SYNC] Sincronização parada")