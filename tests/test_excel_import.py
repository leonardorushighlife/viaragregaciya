import pytest
from io import BytesIO
import openpyxl
from httpx import AsyncClient, ASGITransport

from app.core.database import Base, engine, SessionLocal
from app.models.models import Product
from main import app

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.query(Product).delete()
    db.commit()
    db.close()
    yield

@pytest.mark.asyncio
async def test_excel_product_import():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Наименование продукции", "GTIN", "Наименование фасад", "Наименование маркировка"])
    ws.append(["Конфеты 'Суфле 200г'", "4609999999999", "Суфле 200", "Суфле МАРК"])

    excel_bytes = BytesIO()
    wb.save(excel_bytes)
    excel_bytes.seek(0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"excel_file": ("test_products.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        resp = await ac.post("/facade/products/import-excel", files=files, follow_redirects=True)
        assert resp.status_code == 200

    db = SessionLocal()
    imported_p = db.query(Product).filter(Product.gtin == "4609999999999").first()
    assert imported_p is not None
    assert imported_p.official_name == "Конфеты 'Суфле 200г'"
    assert imported_p.facade_name == "Суфле 200"
    assert imported_p.labeling_name == "Суфле МАРК"
    db.close()
