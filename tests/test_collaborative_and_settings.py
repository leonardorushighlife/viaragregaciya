import pytest
from httpx import AsyncClient, ASGITransport
from datetime import date, timedelta
import uuid

from app.core.database import Base, engine, SessionLocal
from app.models.models import User, AppSetting, Order, Product, Task, OperatorSession, OrderStatus
from main import app

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Clear sessions and orders for clean isolation
    db.query(OperatorSession).delete()
    db.query(Task).delete()
    db.query(Order).delete()
    db.commit()

    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        admin = User(username="admin", role="admin", is_admin=True)
        db.add(admin)

    op1 = db.query(User).filter(User.username == "op1").first()
    if not op1:
        op1 = User(username="op1", role="operator", is_admin=False)
        db.add(op1)

    op2 = db.query(User).filter(User.username == "op2").first()
    if not op2:
        op2 = User(username="op2", role="operator", is_admin=False)
        db.add(op2)

    db.commit()

    prod = db.query(Product).first()
    if not prod:
        prod = Product(official_name="Тестовый продукт", gtin="4600000000000")
        db.add(prod)
        db.commit()

    db.close()
    yield

@pytest.mark.asyncio
async def test_acceptance_criteria_1_and_5_settings():
    db = SessionLocal()
    admin = db.query(User).filter(User.username == "admin").first()
    op1 = db.query(User).filter(User.username == "op1").first()
    admin_id, op1_id = admin.id, op1.id
    db.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/settings?user_id={op1_id}")
        assert resp.status_code == 403

        resp = await ac.get(f"/settings?user_id={admin_id}")
        assert resp.status_code == 200
        assert "Сетевые параметры ролей" in resp.text

        resp = await ac.post(f"/settings?user_id={admin_id}", data={
            "ip_facade": "192.168.1.100",
            "ip_labeling": "192.168.1.101",
            "ip_operator": "192.168.1.102"
        })
        assert resp.status_code == 200
        assert "Настройки сохранены" in resp.text

        db = SessionLocal()
        s_facade = db.query(AppSetting).filter(AppSetting.key == "ip_facade").first()
        assert s_facade is not None
        assert s_facade.value == "192.168.1.100"
        db.close()

@pytest.mark.asyncio
async def test_acceptance_criteria_2_3_4_collaborative_workflow():
    db = SessionLocal()
    op1 = db.query(User).filter(User.username == "op1").first()
    op2 = db.query(User).filter(User.username == "op2").first()
    prod = db.query(Product).first()

    op1_id, op2_id = op1.id, op2.id

    unique_num = f"ORD-COLLAB-{uuid.uuid4().hex[:4].upper()}"
    order = Order(
        order_number=unique_num,
        product_id=prod.id,
        quantity=80,
        shipment_date=date.today() + timedelta(days=2),
        status=OrderStatus.CODES_PRINTED.value
    )
    db.add(order)
    db.commit()

    task = Task(order_id=order.id, quantity_target=80, status="pending")
    db.add(task)
    db.commit()
    task_id, order_id = task.id, order.id
    db.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(f"/operator/task/{task_id}/start?user_id={op1_id}", follow_redirects=False)
        assert resp.status_code == 303
        s1_id = int(resp.headers["location"].split("/")[-1])

        resp = await ac.post(f"/operator/session/{s1_id}/pause?user_id={op1_id}", follow_redirects=True)
        assert resp.status_code == 200

        resp = await ac.post(f"/operator/task/{task_id}/continue?user_id={op2_id}", follow_redirects=False)
        assert resp.status_code == 303
        s2_id = int(resp.headers["location"].split("/")[-1])
        assert s1_id != s2_id

        resp = await ac.get(f"/operator?user_id={op1_id}")
        assert resp.status_code == 200
        assert f"/operator/session/{s1_id}" in resp.text

        resp = await ac.post(f"/operator/session/{s1_id}/resume?user_id={op1_id}", follow_redirects=True)
        assert resp.status_code == 200

        resp = await ac.post(f"/operator/session/{s1_id}/increment?user_id={op1_id}", data={"amount": 30}, follow_redirects=True)
        assert resp.status_code == 200

        resp = await ac.post(f"/operator/session/{s1_id}/finish?user_id={op1_id}", follow_redirects=True)
        assert resp.status_code == 200

        resp = await ac.post(f"/operator/session/{s2_id}/increment?user_id={op2_id}", data={"amount": 50}, follow_redirects=True)
        assert resp.status_code == 200

        resp = await ac.post(f"/operator/session/{s2_id}/finish?user_id={op2_id}", follow_redirects=True)
        assert resp.status_code == 200

        db = SessionLocal()
        o = db.get(Order, order_id)
        t = db.get(Task, task_id)
        assert o.total_applied == 80
        assert t.status == "completed"
        assert o.operators_count == 2
        db.close()
