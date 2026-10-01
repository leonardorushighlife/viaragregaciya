import sys
import os
import uvicorn
import webbrowser
import threading
import time
import socket

def resource_path(relative_path):
    """ Получить абсолютный путь к ресурсу для PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def find_free_port(default_port=8000):
    """ Поиск свободного порта, если 8000 занят """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(('127.0.0.1', default_port)) != 0:
            return default_port
    # If 8000 is busy, get an OS-assigned free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

if __name__ == "__main__":
    # Ensure current directory is app root
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))

    os.chdir(app_dir)

    # Initialise DB tables if database does not exist
    try:
        from app.core.database import Base, engine
        import app.models.models
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Инициализация базы данных: {e}")

    port = find_free_port(8000)
    url = f"http://127.0.0.1:{port}"

    def open_browser():
        time.sleep(1.5)
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()

    from main import app
    print("=" * 60)
    print("  MALVIK-LABEL - Система маркировки и фасовки")
    print(f"  Запуск сервера на {url} ...")
    print("  Для закрытия программы закройте это окно.")
    print("=" * 60)

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
