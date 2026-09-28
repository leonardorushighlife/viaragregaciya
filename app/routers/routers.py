from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, date, timezone

from app.core.database import get_db
from app.models.models import Order, Product, Task, Notification, Report, OrderStatus
from app.services.email_service import send_email
from app.services.chestny_znak import cz_service

templates = Jinja2Templates(directory="templates")

main_router = APIRouter()

@main_router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return RedirectResponse(url="/facade")

# --- 1. FACADE ROUTER ---
facade_router = APIRouter(prefix="/facade")

@facade_router.get("", response_class=HTMLResponse)
async def facade_dashboard(request: Request, db: Session = Depends(get_db)):
    orders = db.query(Order).order_by(Order.created_at.desc()).all()
    products = db.query(Product).all()

    if not products:
        sample_products = [
            Product(official_name="Конфеты 'Мальвик Ассорти' 500г", gtin="4601234567890", facade_name="Мальвик 500г"),
            Product(official_name="Шоколадные батончики 'Карамель' 100г", gtin="4601234567891", facade_name="Батончики 100г"),
            Product(official_name="Карамель леденцовая 'Мята' 1кг", gtin="4601234567892", facade_name="Мята 1кг")
        ]
        db.add_all(sample_products)
        db.commit()
        products = db.query(Product).all()

    return templates.TemplateResponse(request=request, name="facade/dashboard.html", context={
        "role": "facade",
        "orders": orders,
        "products": products,
        "today": date.today()
    })

@facade_router.post("/order/create")
async def create_order(
    order_number: str = Form(...),
    product_id: int = Form(...),
    quantity: int = Form(...),
    shipment_date: str = Form(...),
    notes: str = Form(""),
    send_email_notification: bool = Form(False),
    db: Session = Depends(get_db)
):
    parsed_date = datetime.strptime(shipment_date, "%Y-%m-%d").date()
    new_order = Order(
        order_number=order_number,
        product_id=product_id,
        quantity=quantity,
        shipment_date=parsed_date,
        notes=notes,
        status=OrderStatus.DRAFT.value
    )
    db.add(new_order)
    db.commit()

    if send_email_notification:
        await send_email(
            subject=f"Новый заказ на фасовку #{order_number}",
            body=f"Создан новый заказ #{order_number}. Кол-во: {quantity}. Дата отгрузки: {shipment_date}.",
            recipient="labeling@malvik.ru"
        )

    return RedirectResponse(url="/facade", status_code=303)

@facade_router.post("/order/{order_id}/send-to-labeling")
async def send_to_labeling(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order:
        order.status = OrderStatus.SENT_TO_LABELING.value
        notif = Notification(
            role="LABELING",
            title=f"Заказ #{order.order_number} передан",
            message=f"Заказ #{order.order_number} поступил в отдел маркировки."
        )
        db.add(notif)
        db.commit()
    return RedirectResponse(url="/facade", status_code=303)

@facade_router.post("/product/{product_id}/update-name")
async def update_facade_name(product_id: int, facade_name: str = Form(...), db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product:
        product.facade_name = facade_name
        db.commit()
    return RedirectResponse(url="/facade", status_code=303)


# --- 2. LABELING ROUTER ---
labeling_router = APIRouter(prefix="/labeling")

@labeling_router.get("", response_class=HTMLResponse)
async def labeling_dashboard(request: Request, db: Session = Depends(get_db)):
    orders = db.query(Order).filter(Order.status != OrderStatus.DRAFT.value).order_by(Order.shipment_date.asc()).all()
    return templates.TemplateResponse(request=request, name="labeling/dashboard.html", context={
        "role": "labeling",
        "orders": orders,
        "today": date.today()
    })

@labeling_router.post("/product/{product_id}/update-name")
async def update_labeling_name(product_id: int, labeling_name: str = Form(...), db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product:
        product.labeling_name = labeling_name
        db.commit()
    return RedirectResponse(url="/labeling", status_code=303)

@labeling_router.post("/order/{order_id}/request-codes")
async def request_codes(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order:
        res = await cz_service.request_marking_codes(order.product.gtin, order.quantity)
        order.status = OrderStatus.CODES_REQUESTED.value
        db.commit()
    return RedirectResponse(url="/labeling", status_code=303)

@labeling_router.post("/order/{order_id}/mark-printed")
async def mark_printed(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order:
        order.status = OrderStatus.CODES_PRINTED.value
        existing_task = db.query(Task).filter(Task.order_id == order.id).first()
        if not existing_task:
            new_task = Task(
                order_id=order.id,
                quantity_target=order.quantity,
                status="PENDING"
            )
            db.add(new_task)
        db.commit()
    return RedirectResponse(url="/labeling", status_code=303)

@labeling_router.post("/order/{order_id}/submit-report")
async def submit_report(
    order_id: int,
    total_produced: int = Form(...),
    stickers_used: int = Form(...),
    stickers_wasted: int = Form(0),
    comments: str = Form(""),
    db: Session = Depends(get_db)
):
    order = db.get(Order, order_id)
    if order:
        report = Report(
            order_id=order.id,
            total_produced=total_produced,
            stickers_used=stickers_used,
            stickers_wasted=stickers_wasted,
            comments=comments
        )
        order.status = OrderStatus.COMPLETED.value
        db.add(report)
        db.commit()
    return RedirectResponse(url="/labeling", status_code=303)


# --- 3. OPERATOR ROUTER ---
operator_router = APIRouter(prefix="/operator")

@operator_router.get("", response_class=HTMLResponse)
async def operator_tasks(request: Request, db: Session = Depends(get_db)):
    tasks = db.query(Task).order_by(Task.is_locked.asc(), Task.id.desc()).all()
    return templates.TemplateResponse(request=request, name="operator/tasks.html", context={
        "role": "operator",
        "tasks": tasks
    })

@operator_router.get("/task/{task_id}", response_class=HTMLResponse)
async def task_detail(task_id: int, request: Request, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status == "PENDING" and not task.started_at:
        task.status = "IN_PROGRESS"
        task.started_at = datetime.now(timezone.utc)
        task.order.status = OrderStatus.IN_PACKAGING.value
        db.commit()

    return templates.TemplateResponse(request=request, name="operator/task_detail.html", context={
        "role": "operator",
        "task": task,
        "current_time": datetime.now(timezone.utc)
    })

@operator_router.post("/task/{task_id}/increment")
async def increment_task(task_id: int, amount: int = Form(...), db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task and not task.is_locked:
        task.quantity_completed += amount
        db.commit()
    return RedirectResponse(url=f"/operator/task/{task_id}", status_code=303)

@operator_router.post("/task/{task_id}/finish")
async def finish_task(task_id: int, remaining_stickers: int = Form(...), db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task and not task.is_locked:
        task.remaining_stickers = remaining_stickers
        task.status = "FINISHED"
        task.finished_at = datetime.now(timezone.utc)
        task.is_locked = True
        task.order.status = OrderStatus.PACKAGED.value

        notif = Notification(
            role="LABELING",
            title=f"Фасовка завершена: Заказ #{task.order.order_number}",
            message=f"Оператор завершил фасовку. Наклеено: {task.quantity_completed}, осталось этикеток: {remaining_stickers}."
        )
        db.add(notif)
        db.commit()

    return RedirectResponse(url="/operator", status_code=303)


# --- NOTIFICATIONS API (HTMX Polling) ---
notif_router = APIRouter(prefix="/api/notifications")

@notif_router.get("/unread", response_class=HTMLResponse)
async def get_unread_notifications(request: Request, db: Session = Depends(get_db)):
    notifs = db.query(Notification).filter(Notification.is_read == False).order_by(Notification.created_at.desc()).all()
    return templates.TemplateResponse(request=request, name="components/notification_bell.html", context={
        "notifications": notifs,
        "count": len(notifs)
    })
