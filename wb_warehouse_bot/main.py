import sys
import asyncio
import threading
import logging

# Attempt to import PySide6 or PyQt5
try:
    from PySide6.QtWidgets import QApplication
    QT_EXEC = "exec"
except ImportError:
    try:
        from PyQt5.QtWidgets import QApplication
        QT_EXEC = "exec_"
    except ImportError:
        print("Ошибка: Не установлена библиотека PySide6 или PyQt5. Пожалуйста, установите одну из них.")
        sys.exit(1)

from gui_module import MainWindow
from bot_module import TelegramBot, run_bot

# Configure logging
logging.basicConfig(level=logging.INFO)

def start_bot_thread(bot_instance):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot(bot_instance))

def main():
    app = QApplication(sys.argv)

    # Create the main window first
    window = MainWindow()

    # Define callback for bot
    def on_file_received(file_path):
        # Emit signal to main window from bot thread
        window.file_received.emit(file_path)

    # Initialize bot
    bot = TelegramBot(on_file_received)
    window.bot_instance = bot

    # Run bot in a separate thread
    bot_thread = threading.Thread(target=start_bot_thread, args=(bot,), daemon=True)
    bot_thread.start()

    window.show()

    # Run event loop using correct method for the library
    if QT_EXEC == "exec":
        sys.exit(app.exec())
    else:
        sys.exit(app.exec_())

if __name__ == "__main__":
    main()
