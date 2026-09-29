import logging
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, date, timezone
from typing import Optional

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.models import Order, Product, Task, Notification, Report, OrderStatus, OperatorSession, User
from app.services.email_service import send_email
from app.services.chestny_znak import cz_service

templates = Jinja2Templates(directory="templates")
logger = logging.getLogger("malvik.sessions")

def get_user_for_request(request: Request, db: Session) -> User:
    user = get_current_user(request, db)
    if not user:
        user = db.query(User).filter(User.role == "operator").first() or db.query(User).first()
        if not user:
            user = User(username="op1", role="operator", is_admin=False)
            db.add(user)
            db.commit()
            db.refresh(user)
    return user

main_router = APIRouter()

@main_router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return RedirectResponse(url="/facade")


# --- 1. FACADE ROUTER ---
facade_router = APIRouter(prefix="/facade")

@facade_router.get("", response_class=HTMLResponse)
async def facade_dashboard(request: Request, db: Session = Depends(get_db)):
    current_user = get_user_for_request(request, db)
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
        "current_user": current_user,
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

@facade_router.post("/order/{order_id}/defect")
async def save_order_defect(
    order_id: int,
    defect_qty: int = Form(...),
    redirect_url: str = Form("/facade"),
    db: Session = Depends(get_db)
):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.defect_qty = max(0, defect_qty)
    db.commit()
    logger.info("Updated defect_qty=%s for Order #%s", order.defect_qty, order.order_number)
    return RedirectResponse(url=redirect_url, status_code=303)

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
    current_user = get_user_for_request(request, db)
    orders = db.query(Order).filter(Order.status != OrderStatus.DRAFT.value).order_by(Order.shipment_date.asc()).all()
    return templates.TemplateResponse(request=request, name="labeling/dashboard.html", context={
        "role": "labeling",
        "current_user": current_user,
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
                status="pending"
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
    current_user = get_user_for_request(request, db)

    # Active running sessions belonging to current operator
    my_active_sessions = db.query(OperatorSession).filter(
        OperatorSession.operator_id == current_user.id,
        OperatorSession.status.in_(["running", "paused"])
    ).all()

    # Available tasks: pending OR in_progress where order remaining_codes > 0
    all_tasks = db.query(Task).all()
    available_tasks = []
    for t in all_tasks:
        if t.status in ["pending", "in_progress"] and t.remaining_codes > 0:
            available_tasks.append(t)

    all_users = db.query(User).all()

    return templates.TemplateResponse(request=request, name="operator/tasks.html", context={
        "role": "operator",
        "current_user": current_user,
        "all_users": all_users,
        "my_active_sessions": my_active_sessions,
        "available_tasks": available_tasks,
        "tasks": all_tasks
    })

def check_single_active_session(user_id: int, current_task_id: int, db: Session):
    active = db.query(OperatorSession).filter(
        OperatorSession.operator_id == user_id,
        OperatorSession.status == "running"
    ).first()
    if active and active.order.tasks:
        task = active.order.tasks[0]
        if task.id != current_task_id and not user_id_is_admin(user_id, db):
            raise HTTPException(
                status_code=400,
                detail="У вас уже есть активная (running) сессия на другом заказе. Приостановите или завершите её."
            )
    return active

def user_id_is_admin(user_id: int, db: Session) -> bool:
    user = db.get(User, user_id)
    return bool(user and user.is_admin)

@operator_router.post("/task/{task_id}/start")
async def start_task(task_id: int, request: Request, db: Session = Depends(get_db)):
    current_user = get_user_for_request(request, db)
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.remaining_codes == 0:
        raise HTTPException(status_code=400, detail="Заказ уже выполнен, остаток кодов = 0")

    check_single_active_session(current_user.id, task_id, db)

    existing_session = db.query(OperatorSession).filter(
        OperatorSession.order_id == task.order_id,
        OperatorSession.operator_id == current_user.id,
        OperatorSession.status == "running"
    ).first()

    if not existing_session:
        session = OperatorSession(
            order_id=task.order_id,
            operator_id=current_user.id,
            applied_qty=0,
            status="running",
            started_at=datetime.utcnow()
        )
        db.add(session)
        task.status = "in_progress"
        task.order.status = OrderStatus.IN_PACKAGING.value

        if not task.actual_started_at:
            task.actual_started_at = datetime.utcnow()
        if not task.order.actual_labeling_date:
            task.order.actual_labeling_date = date.today()

        db.commit()
        db.refresh(session)
        logger.info("Operator %s (%s) started session %s for order #%s", current_user.username, current_user.id, session.id, task.order.order_number)
    else:
        session = existing_session

    return RedirectResponse(url=f"/operator/session/{session.id}", status_code=303)

@operator_router.post("/task/{task_id}/continue")
async def continue_task(task_id: int, request: Request, db: Session = Depends(get_db)):
    current_user = get_user_for_request(request, db)
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.remaining_codes == 0:
        raise HTTPException(status_code=400, detail="Заказ уже выполнен, остаток кодов = 0")

    check_single_active_session(current_user.id, task_id, db)

    existing_session = db.query(OperatorSession).filter(
        OperatorSession.order_id == task.order_id,
        OperatorSession.operator_id == current_user.id,
        OperatorSession.status == "running"
    ).first()

    if not existing_session:
        session = OperatorSession(
            order_id=task.order_id,
            operator_id=current_user.id,
            applied_qty=0,
            status="running",
            started_at=datetime.utcnow()
        )
        db.add(session)
        task.status = "in_progress"
        task.order.status = OrderStatus.IN_PACKAGING.value

        if not task.actual_started_at:
            task.actual_started_at = datetime.utcnow()
        if not task.order.actual_labeling_date:
            task.order.actual_labeling_date = date.today()

        db.commit()
        db.refresh(session)
        logger.info("Operator %s (%s) created session %s for in_progress order #%s", current_user.username, current_user.id, session.id, task.order.order_number)
    else:
        session = existing_session

    return RedirectResponse(url=f"/operator/session/{session.id}", status_code=303)

@operator_router.get("/task/{task_id}", response_class=HTMLResponse)
async def task_detail(task_id: int, request: Request, db: Session = Depends(get_db)):
    current_user = get_user_for_request(request, db)
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    session = db.query(OperatorSession).filter(
        OperatorSession.order_id == task.order_id,
        OperatorSession.operator_id == current_user.id,
        OperatorSession.status == "running"
    ).first()

    if not session:
        if task.remaining_codes == 0:
            raise HTTPException(status_code=400, detail="Заказ уже выполнен")
        check_single_active_session(current_user.id, task_id, db)
        session = OperatorSession(
            order_id=task.order_id,
            operator_id=current_user.id,
            applied_qty=0,
            status="running",
            started_at=datetime.utcnow()
        )
        db.add(session)
        task.status = "in_progress"
        task.order.status = OrderStatus.IN_PACKAGING.value
        if not task.actual_started_at:
            task.actual_started_at = datetime.utcnow()
        if not task.order.actual_labeling_date:
            task.order.actual_labeling_date = date.today()
        db.commit()
        db.refresh(session)

    return RedirectResponse(url=f"/operator/session/{session.id}", status_code=303)

@operator_router.get("/session/{session_id}", response_class=HTMLResponse)
async def session_detail(session_id: int, request: Request, db: Session = Depends(get_db)):
    current_user = get_user_for_request(request, db)
    session = db.get(OperatorSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    task = db.query(Task).filter(Task.order_id == session.order_id).first()
    my_sessions = db.query(OperatorSession).filter(
        OperatorSession.order_id == session.order_id,
        OperatorSession.operator_id == current_user.id
    ).order_by(OperatorSession.started_at.desc()).all()

    all_users = db.query(User).all()

    return templates.TemplateResponse(request=request, name="operator/task_detail.html", context={
        "role": "operator",
        "current_user": current_user,
        "all_users": all_users,
        "session": session,
        "task": task,
        "my_sessions": my_sessions,
        "current_time": datetime.utcnow()
    })

@operator_router.post("/session/{session_id}/increment")
async def increment_session(
    session_id: int,
    amount: int = Form(...),
    request: Request = None,
    db: Session = Depends(get_db)
):
    current_user = get_user_for_request(request, db)
    session = db.get(OperatorSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.operator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нельзя изменять чужую сессию")

    if session.status != "running":
        raise HTTPException(status_code=400, detail="Сессия не в статусе running")

    session.applied_qty += amount
    logger.info("Operator %s (%s) incremented session %s by +%s (session_total=%s, order_total=%s/%s)",
                current_user.username, current_user.id, session_id, amount, session.applied_qty, session.order.total_applied, session.order.quantity)

    # Check if total_applied >= order quantity -> auto complete order
    if session.order.total_applied >= session.order.quantity:
        session.status = "completed"
        session.finished_at = datetime.utcnow()
        task = db.query(Task).filter(Task.order_id == session.order_id).first()
        if task:
            task.status = "completed"
            task.actual_completed_at = datetime.utcnow()
        session.order.status = OrderStatus.PACKAGED.value

        other_sessions = db.query(OperatorSession).filter(
            OperatorSession.order_id == session.order_id,
            OperatorSession.status.in_(["running", "paused"])
        ).all()
        for s in other_sessions:
            s.status = "completed"
            s.finished_at = datetime.utcnow()

        notif = Notification(
            role="LABELING",
            title=f"Фасовка завершена: Заказ #{session.order.order_number}",
            message=f"Заказ #{session.order.order_number} полностью упакован ({session.order.total_applied}/{session.order.quantity})."
        )
        db.add(notif)
        logger.info("Order #%s automatically completed (total_applied=%s)", session.order.order_number, session.order.total_applied)

    db.commit()
    return RedirectResponse(url=f"/operator/session/{session_id}", status_code=303)

@operator_router.post("/session/{session_id}/pause")
async def pause_session(
    session_id: int,
    request: Request = None,
    db: Session = Depends(get_db)
):
    current_user = get_user_for_request(request, db)
    session = db.get(OperatorSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.operator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нельзя приостановить чужую сессию")

    if session.status == "running":
        session.status = "paused"
        session.paused_at = datetime.utcnow()
        db.commit()
        logger.info("Operator %s (%s) paused session %s for order #%s", current_user.username, current_user.id, session_id, session.order.order_number)

    return RedirectResponse(url=f"/operator/session/{session_id}", status_code=303)

@operator_router.post("/session/{session_id}/resume")
async def resume_session(
    session_id: int,
    request: Request = None,
    db: Session = Depends(get_db)
):
    current_user = get_user_for_request(request, db)
    session = db.get(OperatorSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.operator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нельзя возобновить чужую сессию")

    task = db.query(Task).filter(Task.order_id == session.order_id).first()
    check_single_active_session(current_user.id, task.id if task else 0, db)

    if session.status == "paused":
        session.status = "running"
        session.paused_at = None
        db.commit()
        logger.info("Operator %s (%s) resumed session %s for order #%s", current_user.username, current_user.id, session_id, session.order.order_number)

    return RedirectResponse(url=f"/operator/session/{session_id}", status_code=303)

@operator_router.post("/session/{session_id}/finish")
async def finish_session(
    session_id: int,
    request: Request = None,
    db: Session = Depends(get_db)
):
    current_user = get_user_for_request(request, db)
    session = db.get(OperatorSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.operator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нельзя завершить чужую сессию")

    if session.status in ["running", "paused"]:
        session.status = "completed"
        session.finished_at = datetime.utcnow()
        logger.info("Operator %s (%s) finished session %s for order #%s (applied=%s)",
                    current_user.username, current_user.id, session_id, session.order.order_number, session.applied_qty)

        # Check if order total_applied >= target quantity
        if session.order.total_applied >= session.order.quantity:
            task = db.query(Task).filter(Task.order_id == session.order_id).first()
            if task:
                task.status = "completed"
                task.actual_completed_at = datetime.utcnow()
            session.order.status = OrderStatus.PACKAGED.value

            notif = Notification(
                role="LABELING",
                title=f"Фасовка завершена: Заказ #{session.order.order_number}",
                message=f"Заказ #{session.order.order_number} полностью упакован."
            )
            db.add(notif)
            logger.info("Order #%s completed upon session finish", session.order.order_number)

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
