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

    db.query(OperatorSession).delete()
    db.query(Task).delete()
    db.query(Order).delete()
    db.commit()

    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        admin = User(username="admin", password_hash="10072025", role="admin", is_admin=True)
        db.add(admin)

    op1 = db.query(User).filter(User.username == "op1").first()
    if not op1:
        op1 = User(username="op1", role="operator", is_admin=False)
        db.add(op1)

    op2 = db.query(User).filter(User.username == "op2").first()
    if not op2:
        op2 = User(username="op2", role="operator", is_admin=False)
        db.add(op2)

    op3 = db.query(User).filter(User.username == "op3").first()
    if not op3:
        op3 = User(username="op3", role="operator", is_admin=False)
        db.add(op3)

    prod = db.query(Product).first()
    if not prod:
        prod = Product(official_name="Тестовый продукт", gtin="4600000000000")
        db.add(prod)

    db.commit()
    db.close()
    yield

@pytest.mark.asyncio
async def test_acceptance_criteria_1_2_3_partial_labeling():
    db = SessionLocal()
    op1 = db.query(User).filter(User.username == "op1").first()
    op2 = db.query(User).filter(User.username == "op2").first()
    op3 = db.query(User).filter(User.username == "op3").first()
    prod = db.query(Product).first()

    op1_id, op2_id, op3_id = op1.id, op2.id, op3.id

    unique_num = f"ORD-PARTIAL-{uuid.uuid4().hex[:4].upper()}"
    order = Order(
        order_number=unique_num,
        product_id=prod.id,
        quantity=120,
        shipment_date=date.today() + timedelta(days=2),
        status=OrderStatus.CODES_PRINTED.value
    )
    db.add(order)
    db.commit()

    task = Task(order_id=order.id, quantity_target=120, status="pending")
    db.add(task)
    db.commit()
    task_id, order_id = task.id, order.id
    db.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Step 1: op1 takes order, sets production date, sticks 30, pauses
        resp = await ac.post(f"/operator/task/{task_id}/start?user_id={op1_id}", follow_redirects=False)
        assert resp.status_code == 303
        s1_id = int(resp.headers["location"].split("/")[-1])

        # Operator sets production date
        prod_date_str = date.today().strftime("%Y-%m-%d")
        resp = await ac.post(f"/operator/session/{s1_id}/production-date?user_id={op1_id}", data={"production_date": prod_date_str}, follow_redirects=True)
        assert resp.status_code == 200

        db = SessionLocal()
        o = db.get(Order, order_id)
        assert o.production_date == date.today()
        db.close()

        resp = await ac.post(f"/operator/session/{s1_id}/increment?user_id={op1_id}", data={"amount": 30}, follow_redirects=True)
        assert resp.status_code == 200

        resp = await ac.post(f"/operator/session/{s1_id}/pause?user_id={op1_id}", follow_redirects=True)
        assert resp.status_code == 200

        db = SessionLocal()
        o = db.get(Order, order_id)
        s1 = db.get(OperatorSession, s1_id)
        assert s1.status == "paused"
        assert o.total_applied == 30
        assert o.remaining_codes == 90
        assert o.actual_labeling_date == date.today()
        db.close()

        # Step 2: op2 continues, sticks 50, finishes session (not order)
        resp = await ac.post(f"/operator/task/{task_id}/continue?user_id={op2_id}", follow_redirects=False)
        assert resp.status_code == 303
        s2_id = int(resp.headers["location"].split("/")[-1])

        resp = await ac.post(f"/operator/session/{s2_id}/increment?user_id={op2_id}", data={"amount": 50}, follow_redirects=True)
        assert resp.status_code == 200

        resp = await ac.post(f"/operator/session/{s2_id}/finish?user_id={op2_id}", follow_redirects=True)
        assert resp.status_code == 200

        db = SessionLocal()
        o = db.get(Order, order_id)
        s2 = db.get(OperatorSession, s2_id)
        assert s2.status == "completed"
        assert o.total_applied == 80
        assert o.remaining_codes == 40
        assert o.status != OrderStatus.COMPLETED.value
        db.close()

        # Step 3: op3 continues, sticks 40, finishes order
        resp = await ac.post(f"/operator/task/{task_id}/continue?user_id={op3_id}", follow_redirects=False)
        assert resp.status_code == 303
        s3_id = int(resp.headers["location"].split("/")[-1])

        resp = await ac.post(f"/operator/session/{s3_id}/increment?user_id={op3_id}", data={"amount": 40}, follow_redirects=True)
        assert resp.status_code == 200

        db = SessionLocal()
        o = db.get(Order, order_id)
        t = db.get(Task, task_id)
        assert o.total_applied == 120
        assert o.remaining_codes == 0
        assert t.status == "completed"
        assert t.actual_completed_at is not None
        db.close()

@pytest.mark.asyncio
async def test_acceptance_criteria_4_5_6():
    db = SessionLocal()
    op1 = db.query(User).filter(User.username == "op1").first()
    prod = db.query(Product).first()

    op1_id = op1.id

    order1 = Order(
        order_number=f"ORD-DEFECT-{uuid.uuid4().hex[:4].upper()}",
        product_id=prod.id,
        quantity=50,
        shipment_date=date.today() + timedelta(days=2),
        status=OrderStatus.CODES_PRINTED.value
    )
    order2 = Order(
        order_number=f"ORD-MULTI-{uuid.uuid4().hex[:4].upper()}",
        product_id=prod.id,
        quantity=50,
        shipment_date=date.today() + timedelta(days=2),
        status=OrderStatus.CODES_PRINTED.value
    )
    db.add_all([order1, order2])
    db.commit()

    task1 = Task(order_id=order1.id, quantity_target=50, status="pending")
    task2 = Task(order_id=order2.id, quantity_target=50, status="pending")
    db.add_all([task1, task2])
    db.commit()

    task1_id, task2_id = task1.id, task2.id
    order1_id = order1.id
    db.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 4. Facade enters defect 5
        resp = await ac.post(f"/facade/order/{order1_id}/defect", data={"defect_qty": 5}, follow_redirects=True)
        assert resp.status_code == 200

        db = SessionLocal()
        o1 = db.get(Order, order1_id)
        assert o1.defect_qty == 5
        db.close()

        # 5. /today summary page
        resp = await ac.get("/today")
        assert resp.status_code == 200
        assert "Сегодня обклеено" in resp.text

        # 6. Single active session limit check
        resp = await ac.post(f"/operator/task/{task1_id}/start?user_id={op1_id}", follow_redirects=False)
        assert resp.status_code == 303

        # Trying to start a second active running session on task2 without pausing task1 session -> 400
        resp = await ac.post(f"/operator/task/{task2_id}/start?user_id={op1_id}")
        assert resp.status_code == 400
        assert "У вас уже есть активная" in resp.text
