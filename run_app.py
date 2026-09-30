import sys
import os
import uvicorn
import webbrowser
import threading
import time

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if __name__ == "__main__":
    # Ensure working directory has templates/static/database if needed
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Auto-open browser after 1.5 seconds
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://127.0.0.1:8000")

    threading.Thread(target=open_browser, daemon=True).start()

    from main import app
    print("Запуск MALVIK-LABEL сервера на http://127.0.0.1:8000 ...")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
