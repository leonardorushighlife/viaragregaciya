import openpyxl
from io import BytesIO
from sqlalchemy.orm import Session
from app.models.models import Product

def import_products_from_excel(file_bytes: bytes, db: Session) -> int:
    wb = openpyxl.load_workbook(filename=BytesIO(file_bytes), data_only=True)
    sheet = wb.active

    imported_count = 0
    header = None

    for row in sheet.iter_rows(values_only=True):
        if not row or all(v is None for v in row):
            continue

        row_str = [str(v).strip().lower() if v is not None else "" for v in row]
        if any("наименование" in cell or "название" in cell or "gtin" in cell for cell in row_str):
            header = row_str
            continue

        if not header:
            official_name = str(row[0]).strip() if row[0] is not None else ""
            gtin = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
            facade_name = str(row[2]).strip() if len(row) > 2 and row[2] is not None else None
            labeling_name = str(row[3]).strip() if len(row) > 3 and row[3] is not None else None
        else:
            official_name, gtin, facade_name, labeling_name = "", "", None, None
            for idx, cell_val in enumerate(row):
                if cell_val is None or idx >= len(header):
                    continue
                col_name = header[idx]
                val_str = str(cell_val).strip()
                # Clean excel formulas like ="text" or =""text""
                if val_str.startswith('="') and val_str.endswith('"'):
                    val_str = val_str[2:-1].strip()
                if val_str.startswith('"') and val_str.endswith('"'):
                    val_str = val_str[1:-1].strip()

                if "фасад" in col_name:
                    facade_name = val_str
                elif "маркировк" in col_name:
                    labeling_name = val_str
                elif "gtin" in col_name or "штрихкод" in col_name:
                    gtin = val_str
                elif "продукци" in col_name or "официальн" in col_name or "наименование" in col_name or "название" in col_name:
                    if not official_name:
                        official_name = val_str

        if official_name:
            existing = db.query(Product).filter(Product.official_name == official_name).first()
            if not existing and gtin:
                existing = db.query(Product).filter(Product.gtin == gtin).first()

            if not existing:
                new_prod = Product(
                    official_name=official_name,
                    gtin=gtin or None,
                    facade_name=facade_name,
                    labeling_name=labeling_name
                )
                db.add(new_prod)
            else:
                if gtin:
                    existing.gtin = gtin
                if facade_name:
                    existing.facade_name = facade_name
                if labeling_name:
                    existing.labeling_name = labeling_name

            imported_count += 1

    db.commit()
    return imported_count
