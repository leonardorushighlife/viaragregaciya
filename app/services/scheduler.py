from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, date, timedelta
from app.core.database import SessionLocal
from app.models.models import Order, Notification, OrderStatus

scheduler = AsyncIOScheduler()

async def check_shipment_deadlines():
    """Фоновая задача: проверяет заказы, до отгрузки которых осталось <= 2 дней"""
    db = SessionLocal()
    try:
        today = date.today()
        target_date = today + timedelta(days=2)

        urgent_orders = db.query(Order).filter(
            Order.shipment_date <= target_date,
            Order.shipment_date >= today,
            Order.status.in_([
                OrderStatus.SENT_TO_LABELING.value,
                OrderStatus.CODES_REQUESTED.value,
                OrderStatus.CODES_PRINTED.value,
                OrderStatus.IN_PACKAGING.value
            ])
        ).all()

        for order in urgent_orders:
            days_left = (order.shipment_date - today).days
            title = f"Срочный заказ {order.order_number}"
            msg = f"Заказ #{order.order_number} отгружается через {days_left} дн. ({order.shipment_date}). Статус: {order.status}"

            # Проверяем, не было ли уже создано такое уведомление сегодня
            existing = db.query(Notification).filter(
                Notification.title == title,
                Notification.created_at >= datetime.combine(today, datetime.min.time())
            ).first()

            if not existing:
                notif = Notification(
                    role="LABELING",
                    title=title,
                    message=msg
                )
                db.add(notif)
        db.commit()
    except Exception as e:
        print(f"Error checking deadlines: {e}")
        db.rollback()
    finally:
        db.close()

def start_scheduler():
    scheduler.add_job(check_shipment_deadlines, 'interval', minutes=30)
    scheduler.start()
