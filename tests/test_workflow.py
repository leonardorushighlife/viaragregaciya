import pytest
from httpx import AsyncClient, ASGITransport
from datetime import date, timedelta
import uuid

from app.core.database import Base, engine, SessionLocal
from app.models.models import Order, Product, Task, OrderStatus
from main import app

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield

@pytest.mark.asyncio
async def test_full_workflow():
    unique_order_num = f"TEST-{uuid.uuid4().hex[:6].upper()}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/facade")
        assert response.status_code == 200

        db = SessionLocal()
        product = db.query(Product).first()
        db.close()

        shipment_date_str = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")

        response = await ac.post("/facade/order/create", data={
            "order_number": unique_order_num,
            "product_id": product.id,
            "quantity": 50,
            "shipment_date": shipment_date_str,
            "notes": "Test order workflow",
            "send_email_notification": "false"
        }, follow_redirects=True)
        assert response.status_code == 200

        db = SessionLocal()
        order = db.query(Order).filter(Order.order_number == unique_order_num).first()
        assert order is not None
        assert order.status == OrderStatus.DRAFT.value
        order_id = order.id
        db.close()

        response = await ac.post(f"/facade/order/{order_id}/send-to-labeling", follow_redirects=True)
        assert response.status_code == 200

        db = SessionLocal()
        order = db.get(Order, order_id)
        assert order.status == OrderStatus.SENT_TO_LABELING.value
        db.close()

        response = await ac.post(f"/labeling/order/{order_id}/request-codes", follow_redirects=True)
        assert response.status_code == 200

        db = SessionLocal()
        order = db.get(Order, order_id)
        assert order.status == OrderStatus.CODES_REQUESTED.value
        db.close()

        response = await ac.post(f"/labeling/order/{order_id}/mark-printed", follow_redirects=True)
        assert response.status_code == 200

        db = SessionLocal()
        order = db.get(Order, order_id)
        assert order.status == OrderStatus.CODES_PRINTED.value
        task = db.query(Task).filter(Task.order_id == order_id).first()
        assert task is not None
        task_id = task.id
        db.close()

        response = await ac.get(f"/operator/task/{task_id}")
        assert response.status_code == 200

        response = await ac.post(f"/operator/task/{task_id}/increment", data={"amount": 10}, follow_redirects=True)
        assert response.status_code == 200

        db = SessionLocal()
        task = db.get(Task, task_id)
        assert task.quantity_completed == 10
        db.close()

        response = await ac.post(f"/operator/task/{task_id}/finish", data={"remaining_stickers": 40}, follow_redirects=True)
        assert response.status_code == 200

        db = SessionLocal()
        task = db.get(Task, task_id)
        assert task.is_locked == True
        assert task.remaining_stickers == 40
        assert task.order.status == OrderStatus.PACKAGED.value
        db.close()

        response = await ac.post(f"/labeling/order/{order_id}/submit-report", data={
            "total_produced": 50,
            "stickers_used": 50,
            "stickers_wasted": 2,
            "comments": "Done successfully"
        }, follow_redirects=True)
        assert response.status_code == 200

        db = SessionLocal()
        order = db.get(Order, order_id)
        assert order.status == OrderStatus.COMPLETED.value
        db.close()
