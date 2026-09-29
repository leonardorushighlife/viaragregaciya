import sys
from datetime import date, datetime, timedelta
from app.core.database import SessionLocal, engine, Base
from app.models.models import User, AppSetting, Product, Order, Task, OperatorSession, OrderStatus

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Clear existing data in seed
        db.query(OperatorSession).delete()
        db.query(Task).delete()
        db.query(Order).delete()
        db.query(Product).delete()
        db.query(AppSetting).delete()
        db.query(User).delete()
        db.commit()

        # 1. Create Users (1 Admin with password 10072025, 2 Operators)
        admin = User(username="admin", password_hash="10072025", role="admin", is_admin=True)
        op1 = User(username="op1", role="operator", is_admin=False)
        op2 = User(username="op2", role="operator", is_admin=False)
        db.add_all([admin, op1, op2])
        db.commit()

        # 2. Create Default App Settings
        settings = [
            AppSetting(section="network", key="ip_facade", value="192.168.1.10"),
            AppSetting(section="network", key="ip_labeling", value="192.168.1.11"),
            AppSetting(section="network", key="ip_operator", value="192.168.1.20"),
        ]
        db.add_all(settings)

        # 3. Create Sample Product & Order
        product = Product(
            official_name="Конфеты 'Мальвик Ассорти' 500г",
            facade_name="Мальвик 500г",
            labeling_name="Ассорти 500г",
            gtin="4601234567890"
        )
        db.add(product)
        db.commit()

        order = Order(
            order_number="ORD-2026-SEED",
            product_id=product.id,
            quantity=120,
            defect_qty=2,
            production_date=date.today(),
            actual_labeling_date=date.today(),
            shipment_date=date.today() + timedelta(days=5),
            status=OrderStatus.IN_PACKAGING.value,
            notes="Демонстрационный заказ для проверки совместной работы"
        )
        db.add(order)
        db.commit()

        # 4. Create Task in status 'in_progress'
        task = Task(
            order_id=order.id,
            quantity_target=120,
            status="in_progress",
            actual_started_at=datetime.utcnow() - timedelta(minutes=30)
        )
        db.add(task)
        db.commit()

        # 5. Create 2 Active Sessions for the order (op1 and op2)
        session1 = OperatorSession(
            order_id=order.id,
            operator_id=op1.id,
            applied_qty=30,
            started_at=datetime.utcnow() - timedelta(minutes=30),
            status="running"
        )
        session2 = OperatorSession(
            order_id=order.id,
            operator_id=op2.id,
            applied_qty=20,
            started_at=datetime.utcnow() - timedelta(minutes=15),
            status="paused",
            paused_at=datetime.utcnow() - timedelta(minutes=5)
        )
        db.add_all([session1, session2])
        db.commit()

        print("Successfully seeded database:")
        print(f" - Admin user: {admin.username} (id={admin.id}, password=10072025, is_admin={admin.is_admin})")
        print(f" - Operator 1: {op1.username} (id={op1.id})")
        print(f" - Operator 2: {op2.username} (id={op2.id})")
        print(f" - Order #{order.order_number} (status={order.status}, total_applied={order.total_applied}/120, remaining={order.remaining_codes})")
        print(f" - Active sessions: 1 (op1: {session1.applied_qty}), 2 (op2: {session2.applied_qty})")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    seed()
