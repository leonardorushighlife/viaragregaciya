import openpyxl
from openpyxl import load_workbook
import os
import logging

class ExcelHandler:
    def __init__(self, filepath):
        self.filepath = filepath
        self.workbook = load_workbook(filepath)
        self.sheet = self.workbook.active
        self.headers = [cell.value for cell in self.sheet[1]]

        # Try to find "КИЗ" column case-insensitively
        self.kiz_col_idx = -1
        for i, h in enumerate(self.headers):
            if h and str(h).strip().upper() == "КИЗ":
                self.kiz_col_idx = i + 1
                break

        # If not found, try to look for common variations or just use the last column + 1
        if self.kiz_col_idx == -1:
            logging.warning("Column 'КИЗ' not found in Excel file.")

    def get_data(self):
        data = []
        # Skip header
        for row in self.sheet.iter_rows(min_row=2, values_only=True):
            data.append(list(row))
        return data

    def save_kiz(self, row_idx, kiz_value):
        # row_idx is 0-based for data (which starts at row 2)
        if self.kiz_col_idx != -1:
            self.sheet.cell(row=row_idx + 2, column=self.kiz_col_idx).value = kiz_value
        else:
            # If KIZ column wasn't found, we could append it,
            # but per requirements we should "find" it.
            # Let's append it if it doesn't exist to be safe?
            # The requirement says "находить колонку", so we assume it exists.
            pass

    def save_file(self, output_path=None):
        if output_path is None:
            output_path = self.filepath
        self.workbook.save(output_path)
        return output_path

    def get_column_index(self, col_name):
        for i, h in enumerate(self.headers):
            if h and str(h).strip().upper() == col_name.upper():
                return i
        return -1
