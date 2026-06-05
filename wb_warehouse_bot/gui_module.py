import sys
import os
import datetime
import logging
import asyncio

# Attempt to import PySide6 or PyQt5
try:
    from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout,
                                 QWidget, QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
                                 QLineEdit, QLabel, QTextEdit, QMessageBox, QDialog)
    from PySide6.QtCore import Qt, Signal, QObject, Slot
    QT_VERSION = "PySide6"
except ImportError:
    try:
        from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout,
                                     QWidget, QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
                                     QLineEdit, QLabel, QTextEdit, QMessageBox, QDialog)
        from PyQt5.QtCore import Qt, pyqtSignal as Signal, QObject, pyqtSlot as Slot
        QT_VERSION = "PyQt5"
    except ImportError:
        print("Ошибка: Не установлена библиотека PySide6 или PyQt5. Пожалуйста, установите одну из них.")
        sys.exit(1)

from excel_handler import ExcelHandler
from stats_manager import save_assembly_result, get_statistics, format_duration

# Mapping for Russian keyboard layout to English QWERTY
RU_TO_EN = {
    'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p', 'х': '[', 'ъ': ']',
    'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k', 'д': 'l', 'ж': ';', 'э': "'",
    'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm', 'б': ',', 'ю': '.', '.': '/',
    'Й': 'Q', 'Ц': 'W', 'У': 'E', 'К': 'R', 'Е': 'T', 'Н': 'Y', 'Г': 'U', 'Ш': 'I', 'Щ': 'O', 'З': 'P', 'Х': '{', 'Ъ': '}',
    'Ф': 'A', 'Ы': 'S', 'В': 'D', 'А': 'F', 'П': 'G', 'Р': 'H', 'О': 'J', 'Л': 'K', 'Д': 'L', 'Ж': ':', 'Э': '"',
    'Я': 'Z', 'Ч': 'X', 'С': 'C', 'М': 'V', 'И': 'B', 'Т': 'N', 'Ь': 'M', 'Б': '<', 'Ю': '>'
}

def translate_to_en(text):
    return "".join(RU_TO_EN.get(c, c) for c in text)

class StatsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Статистика сборок")
        self.resize(400, 300)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        stats = get_statistics()

        if not stats:
            layout.addWidget(QLabel("История сборок пуста."))
        else:
            for period, name in [('week', 'За последнюю неделю'), ('month', 'За последний месяц'), ('total', 'Всего')]:
                p_stats = stats[period]
                group_box = QLabel(f"<b>{name}:</b><br>"
                                   f"Сборок: {p_stats['count']}<br>"
                                   f"Товаров: {p_stats['items']}<br>"
                                   f"Времени: {format_duration(p_stats['time'])}")
                layout.addWidget(group_box)

        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

class OrderAssemblyWindow(QDialog):
    def __init__(self, excel_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Сборка заказа: {os.path.basename(excel_path)}")
        self.resize(800, 600)
        self.excel_path = excel_path
        self.handler = ExcelHandler(excel_path)
        self.start_time = None
        self.is_collecting = False

        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.handler.headers))
        self.table.setHorizontalHeaderLabels(self.handler.headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        # Scanner input
        scan_layout = QHBoxLayout()
        scan_layout.addWidget(QLabel("Сканер:"))
        self.scan_input = QLineEdit()
        self.scan_input.setPlaceholderText("Отсканируйте КИЗ здесь...")
        self.scan_input.returnPressed.connect(self.process_scan)
        self.scan_input.setEnabled(False)
        scan_layout.addWidget(self.scan_input)
        layout.addLayout(scan_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Начать сборку")
        self.start_btn.clicked.connect(self.start_assembly)
        btn_layout.addWidget(self.start_btn)

        self.finish_btn = QPushButton("Завершить сборку")
        self.finish_btn.clicked.connect(self.finish_assembly)
        self.finish_btn.setEnabled(False)
        btn_layout.addWidget(self.finish_btn)

        layout.addLayout(btn_layout)

    def load_data(self):
        data = self.handler.get_data()
        self.table.setRowCount(len(data))
        for r_idx, row in enumerate(data):
            for c_idx, val in enumerate(row):
                item = QTableWidgetItem(str(val) if val is not None else "")
                self.table.setItem(r_idx, c_idx, item)

    def start_assembly(self):
        if self.handler.kiz_col_idx == -1:
            QMessageBox.critical(self, "Ошибка", "Колонка 'КИЗ' не найдена в файле!")
            return

        self.start_time = datetime.datetime.now()
        self.is_collecting = True
        self.scan_input.setEnabled(True)
        self.scan_input.setFocus()
        self.start_btn.setEnabled(False)
        self.finish_btn.setEnabled(True)
        self.parent().log(f"Сборка начата в {self.start_time.strftime('%H:%M:%S')}")

    def process_scan(self):
        if not self.is_collecting:
            return

        raw_kiz = self.scan_input.text().strip()
        if not raw_kiz:
            return

        # Convert Russian input to English equivalents
        kiz = translate_to_en(raw_kiz)

        kiz_col = self.handler.kiz_col_idx - 1
        if kiz_col < 0:
            QMessageBox.critical(self, "Ошибка", "Колонка 'КИЗ' не найдена!")
            return

        found = False
        for r in range(self.table.rowCount()):
            item = self.table.item(r, kiz_col)
            if not item or not item.text().strip():
                # Fill it
                self.table.setItem(r, kiz_col, QTableWidgetItem(kiz))
                self.handler.save_kiz(r, kiz)

                # Update status if exists
                status_col = self.handler.get_column_index("Статус")
                if status_col != -1:
                    self.table.setItem(r, status_col, QTableWidgetItem("Собрано"))

                found = True
                self.parent().log(f"Киз {kiz} добавлен в строку {r+1}")
                break

        if not found:
            QMessageBox.warning(self, "Внимание", "Все позиции уже собраны!")

        self.scan_input.clear()
        self.scan_input.setFocus()

    def finish_assembly(self):
        kiz_col = self.handler.kiz_col_idx - 1
        all_done = True
        item_count = 0
        for r in range(self.table.rowCount()):
            item = self.table.item(r, kiz_col)
            if not item or not item.text().strip():
                all_done = False
            else:
                item_count += 1

        if not all_done:
            reply = QMessageBox.question(self, "Завершение", "Не все позиции собраны. Все равно завершить?",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return

        end_time = datetime.datetime.now()
        duration = end_time - self.start_time
        duration_seconds = duration.total_seconds()

        stats = (f"Отчет о сборке:\n"
                 f"Файл: {os.path.basename(self.excel_path)}\n"
                 f"Начало: {self.start_time.strftime('%H:%M:%S')}\n"
                 f"Окончание: {end_time.strftime('%H:%M:%S')}\n"
                 f"Длительность: {format_duration(duration_seconds)}\n"
                 f"Всего позиций: {self.table.rowCount()}")

        self.parent().log("Сборка завершена. Сохранение в историю и отправка отчета...")

        # Save to history
        save_assembly_result(item_count, duration_seconds)

        # Save file
        output_path = self.handler.save_file()

        # Notify parent to send file and stats to Telegram
        self.parent().on_assembly_finished(output_path, stats)
        self.accept()

class MainWindow(QMainWindow):
    file_received = Signal(str)

    def __init__(self, bot_instance=None):
        super().__init__()
        self.bot_instance = bot_instance
        self.setWindowTitle(f"WB Warehouse Automation ({QT_VERSION})")
        self.resize(600, 450)

        self.init_ui()
        self.file_received.connect(self.open_assembly_window)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        btn_layout = QHBoxLayout()
        self.load_btn = QPushButton("Загрузить заказ (Excel)")
        self.load_btn.clicked.connect(self.manual_load)
        btn_layout.addWidget(self.load_btn)

        self.stats_btn = QPushButton("Показать статистику")
        self.stats_btn.clicked.connect(self.show_stats)
        btn_layout.addWidget(self.stats_btn)

        layout.addLayout(btn_layout)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.log(f"Программа запущена ({QT_VERSION}). Ожидание файлов...")

    def log(self, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{timestamp}] {message}")

    def manual_load(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите файл заказа", "", "Excel Files (*.xlsx)")
        if file_path:
            self.open_assembly_window(file_path)

    def show_stats(self):
        dialog = StatsDialog(self)
        dialog.exec()

    @Slot(str)
    def open_assembly_window(self, file_path):
        self.log(f"Открытие окна сборки для: {file_path}")
        dialog = OrderAssemblyWindow(file_path, self)
        dialog.exec()

    def on_assembly_finished(self, file_path, stats):
        if self.bot_instance and self.bot_instance.loop:
            self.log("Отправка результата и отчета в Telegram...")
            asyncio.run_coroutine_threadsafe(
                self.bot_instance.send_result(file_path, stats),
                self.bot_instance.loop
            )
        else:
            self.log("Бот не запущен, файл не отправлен.")
