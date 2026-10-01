import logging
from fastapi import APIRouter, Depends, Form, Request, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, date, time, timezone, timedelta
from typing import Optional

from app.core.database import get_db
from app.core.auth import get_current_user, ADMIN_PASSWORD
from app.models.models import Order, Product, Task, Notification, Report, OrderStatus, OperatorSession, User
from app.services.email_service import send_email
from app.services.chestny_znak import cz_service
from app.services.excel_import import import_products_from_excel

import sys
import os

def get_templates_dir():
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    t_dir = os.path.join(base, "templates")
    if not os.path.exists(t_dir):
        try:
            t_dir = os.path.join(sys._MEIPASS, "templates")
        except Exception:
            pass
    return t_dir

templates = Jinja2Templates(directory=get_templates_dir())
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
async def index(request: Request, db: Session = Depends(get_db)):
    saved_role = request.cookies.get("saved_role")
    if saved_role == "facade":
        return RedirectResponse(url="/facade", status_code=303)
    elif saved_role == "labeling":
        return RedirectResponse(url="/labeling", status_code=303)
    elif saved_role == "operator":
        return RedirectResponse(url="/operator", status_code=303)
    elif saved_role == "warehouse":
        return RedirectResponse(url="/warehouse", status_code=303)
    elif saved_role == "admin":
        return RedirectResponse(url="/settings", status_code=303)
    else:
        return RedirectResponse(url="/select-role", status_code=303)

@main_router.get("/select-role", response_class=HTMLResponse)
async def select_role_page(request: Request):
    return templates.TemplateResponse(request=request, name="select_role.html", context={
        "error_msg": None
    })

@main_router.post("/select-role", response_class=HTMLResponse)
async def select_role_post(
    request: Request,
    role: str = Form(...),
    operator_username: Optional[str] = Form(None),
    admin_password: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    target_url = "/select-role"
    user_to_set = None

    if role == "operator":
        op_name = operator_username or "op1"
        user_to_set = db.query(User).filter(User.username == op_name).first()
        if not user_to_set:
            user_to_set = User(username=op_name, role="operator", is_admin=False)
            db.add(user_to_set)
            db.commit()
            db.refresh(user_to_set)
        target_url = "/operator"

    elif role == "admin":
        if admin_password != ADMIN_PASSWORD:
            return templates.TemplateResponse(request=request, name="select_role.html", context={
                "error_msg": "Неверный пароль администратора. Введите правильный пароль (10072025)."
            })
        user_to_set = db.query(User).filter(User.is_admin == True).first()
        if not user_to_set:
            user_to_set = User(username="admin", password_hash=ADMIN_PASSWORD, role="admin", is_admin=True)
            db.add(user_to_set)
            db.commit()
            db.refresh(user_to_set)
        target_url = "/settings"

    elif role == "facade":
        user_to_set = db.query(User).filter(User.role == "facade").first()
        if not user_to_set:
            user_to_set = User(username="facade_mgr", role="facade", is_admin=False)
            db.add(user_to_set)
            db.commit()
            db.refresh(user_to_set)
        target_url = "/facade"

    elif role == "labeling":
        user_to_set = db.query(User).filter(User.role == "labeling").first()
        if not user_to_set:
            user_to_set = User(username="labeling_mgr", role="labeling", is_admin=False)
            db.add(user_to_set)
            db.commit()
            db.refresh(user_to_set)
        target_url = "/labeling"

    elif role == "warehouse":
        user_to_set = db.query(User).filter(User.role == "warehouse").first()
        if not user_to_set:
            user_to_set = User(username="warehouse_mgr", role="warehouse", is_admin=False)
            db.add(user_to_set)
            db.commit()
            db.refresh(user_to_set)
        target_url = "/warehouse"

    response = RedirectResponse(url=target_url, status_code=303)
    if user_to_set:
        response.set_cookie("user_id", str(user_to_set.id), max_age=30*24*3600)
        response.set_cookie("saved_role", role, max_age=30*24*3600)
    return response

@main_router.get("/logout")
async def logout():
    response = RedirectResponse(url="/select-role", status_code=303)
    response.delete_cookie("user_id")
    response.delete_cookie("saved_role")
    return response


# --- 0. WAREHOUSE ROUTER ---
warehouse_router = APIRouter(prefix="/warehouse")

@warehouse_router.get("", response_class=HTMLResponse)
async def warehouse_dashboard(request: Request, db: Session = Depends(get_db)):
    current_user = get_user_for_request(request, db)
    orders = db.query(Order).filter(Order.status.in_(["SENT_TO_WAREHOUSE", "ACCEPTED_AT_WAREHOUSE", OrderStatus.COMPLETED.value])).order_by(Order.shipment_date.asc()).all()
    return templates.TemplateResponse(request=request, name="warehouse/dashboard.html", context={
        "role": "warehouse",
        "current_user": current_user,
        "orders": orders,
        "today": date.today()
    })

@warehouse_router.post("/order/{order_id}/accept")
async def accept_warehouse_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order:
        order.status = "ACCEPTED_AT_WAREHOUSE"

        # Global notification to all roles that order is accepted at warehouse
        notif = Notification(
            role="ALL",
            title=f"Принят на склад: Заказ #{order.order_number}",
            message=f"Склад подтвердил приемку заказа #{order.order_number} ({order.product.official_name}). Фактическое кол-во: {order.total_applied} шт."
        )
        db.add(notif)
        db.commit()
        logger.info("Warehouse accepted order #%s", order.order_number)

    return RedirectResponse(url="/warehouse", status_code=303)


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

    current_hour = datetime.now().hour
    is_after_12 = current_hour >= 12
    max_prod_date = date.today() + timedelta(days=20)

    return templates.TemplateResponse(request=request, name="facade/dashboard.html", context={
        "role": "facade",
        "current_user": current_user,
        "orders": orders,
        "products": products,
        "today": date.today(),
        "max_prod_date": max_prod_date,
        "is_after_12": is_after_12
    })

from app.models.models import Order, Product, Task, Notification, Report, OrderStatus, OperatorSession, User, OrderItem

@facade_router.post("/order/create")
async def create_order(
    request: Request,
    order_number: str = Form(...),
    urgency_reason: Optional[str] = Form(""),
    notes: str = Form(""),
    send_email_notification: bool = Form(False),
    db: Session = Depends(get_db)
):
    form_data = await request.form()
    item_product_ids = form_data.getlist("item_product_id")
    item_quantities = form_data.getlist("item_quantity")
    item_shipment_dates = form_data.getlist("item_shipment_date")
    item_production_dates = form_data.getlist("item_production_date")

    # Fallback to single product fields if form submitted without list fields
    if not item_product_ids:
        product_id = form_data.get("product_id")
        quantity = form_data.get("quantity")
        shipment_date = form_data.get("shipment_date")
        production_date = form_data.get("production_date")
        if product_id:
            item_product_ids = [product_id]
            item_quantities = [quantity]
            item_shipment_dates = [shipment_date]
            item_production_dates = [production_date]

    if not item_product_ids:
        raise HTTPException(status_code=400, detail="В заказе должен быть указан хотя бы один товар.")

    order_created_date = date.today()
    max_allowed_date = order_created_date + timedelta(days=20)

    parsed_items = []
    total_qty = 0
    earliest_shipment_date = None
    first_product_id = int(item_product_ids[0])

    for i in range(len(item_product_ids)):
        pid = int(item_product_ids[i])
        qty = int(item_quantities[i])
        s_date = datetime.strptime(item_shipment_dates[i], "%Y-%m-%d").date()
        p_date = datetime.strptime(item_production_dates[i], "%Y-%m-%d").date() if item_production_dates[i] else None

        if p_date and p_date > max_allowed_date:
            raise HTTPException(
                status_code=400,
                detail=f"Заказ кода можно делать максимум за 20 дней до ожидаемой даты производства. Позиция #{i+1}: дата производства {p_date.strftime('%d.%m.%Y')}, допустимо не позднее {max_allowed_date.strftime('%d.%m.%Y')}."
            )

        total_qty += qty
        if earliest_shipment_date is None or s_date < earliest_shipment_date:
            earliest_shipment_date = s_date

        parsed_items.append({
            "product_id": pid,
            "quantity": qty,
            "shipment_date": s_date,
            "production_date": p_date
        })

    # Check if order created after 12:00
    if datetime.now().hour >= 12 and not urgency_reason:
        urgency_reason = "Заказ создан после 12:00 (срочный заказ)"

    new_order = Order(
        order_number=order_number,
        product_id=first_product_id,
        quantity=total_qty,
        shipment_date=earliest_shipment_date,
        production_date=parsed_items[0]["production_date"],
        urgency_reason=urgency_reason,
        notes=notes,
        status=OrderStatus.DRAFT.value
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    for item_data in parsed_items:
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=item_data["product_id"],
            quantity=item_data["quantity"],
            shipment_date=item_data["shipment_date"],
            production_date=item_data["production_date"]
        )
        db.add(order_item)

    db.commit()

    if send_email_notification:
        await send_email(
            subject=f"Новый заказ на фасовку #{order_number}",
            body=f"Создан новый многопозиционный заказ #{order_number}. Позиций: {len(parsed_items)}, общее кол-во: {total_qty}. Срочность: {urgency_reason or 'Нет'}.",
            recipient="labeling@malvik.ru"
        )

    return RedirectResponse(url="/facade", status_code=303)

@facade_router.post("/products/import-excel")
async def import_excel_products(
    excel_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    contents = await excel_file.read()
    count = import_products_from_excel(contents, db)
    logger.info("Imported %s products from Excel file %s", count, excel_file.filename)
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

@facade_router.post("/order/{order_id}/send-to-warehouse")
async def send_to_warehouse(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order:
        order.status = "SENT_TO_WAREHOUSE"

        # Notification to Labeling department that products are transferred to warehouse and need to be introduced into circulation
        notif_labeling = Notification(
            role="LABELING",
            title=f"Передача на склад и ввод в оборот: Заказ #{order.order_number}",
            message=f"Заказ #{order.order_number} передан на склад. Фактически изготовлено и обклеено: {order.total_applied} шт. Пожалуйста, подайте данные о вводе в оборот в Честный Знак."
        )

        # Notification to Warehouse
        notif_warehouse = Notification(
            role="WAREHOUSE",
            title=f"Поступление товара на склад: Заказ #{order.order_number}",
            message=f"На склад передан заказ #{order.order_number} ({order.product.official_name}). Фактическое количество: {order.total_applied} шт."
        )

        db.add(notif_labeling)
        db.add(notif_warehouse)
        db.commit()
        logger.info("Order #%s sent to warehouse (total_applied=%s)", order.order_number, order.total_applied)

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
    products = db.query(Product).all()
    max_prod_date = date.today() + timedelta(days=20)
    return templates.TemplateResponse(request=request, name="labeling/dashboard.html", context={
        "role": "labeling",
        "current_user": current_user,
        "orders": orders,
        "products": products,
        "today": date.today(),
        "max_prod_date": max_prod_date
    })

@labeling_router.get("/order/{order_id}", response_class=HTMLResponse)
async def labeling_order_detail(order_id: int, request: Request, db: Session = Depends(get_db)):
    current_user = get_user_for_request(request, db)
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return templates.TemplateResponse(request=request, name="labeling/order_detail.html", context={
        "role": "labeling",
        "current_user": current_user,
        "order": order,
        "today": date.today()
    })

@labeling_router.post("/order/create")
async def create_labeling_order(
    order_number: str = Form(...),
    product_id: int = Form(...),
    quantity: int = Form(...),
    shipment_date: str = Form(...),
    production_date: Optional[str] = Form(None),
    notes: str = Form(""),
    db: Session = Depends(get_db)
):
    order_created_date = date.today()
    parsed_shipment_date = datetime.strptime(shipment_date, "%Y-%m-%d").date()
    parsed_production_date = datetime.strptime(production_date, "%Y-%m-%d").date() if production_date else None

    # Validate production_date <= order_date + 20 days
    if parsed_production_date:
        max_allowed_date = order_created_date + timedelta(days=20)
        if parsed_production_date > max_allowed_date:
            raise HTTPException(
                status_code=400,
                detail=f"Заказ кода можно делать максимум за 20 дней до ожидаемой даты производства. Дата заказа: {order_created_date.strftime('%d.%m.%Y')}. Выбранная дата производства: {parsed_production_date.strftime('%d.%m.%Y')}, допустимо не позднее {max_allowed_date.strftime('%d.%m.%Y')}."
            )

    new_order = Order(
        order_number=order_number,
        product_id=product_id,
        quantity=quantity,
        shipment_date=parsed_shipment_date,
        production_date=parsed_production_date,
        notes=notes,
        status=OrderStatus.SENT_TO_LABELING.value
    )
    db.add(new_order)
    db.commit()
    logger.info("Labeling created order #%s", order_number)
    return RedirectResponse(url="/labeling", status_code=303)

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

        # Create notification to perform introducing into circulation (Ввод в оборот)
        notif = Notification(
            role="LABELING",
            title=f"Отчет о нанесении подтвержден: Заказ #{order.order_number}",
            message=f"Отчет о нанесении для заказа #{order.order_number} подтвержден. Необходимо подать данные о вводе кодов маркировки в оборот (Честный Знак)."
        )
        db.add(notif)

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
    if active and active.order and active.order.tasks:
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

@operator_router.post("/session/{session_id}/production-date")
async def set_production_date(
    session_id: int,
    production_date: str = Form(...),
    request: Request = None,
    db: Session = Depends(get_db)
):
    current_user = get_user_for_request(request, db)
    session = db.get(OperatorSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        parsed_date = datetime.strptime(production_date, "%Y-%m-%d").date()
        session.order.production_date = parsed_date
        db.commit()
        logger.info("Operator %s set production_date=%s for Order #%s", current_user.username, parsed_date, session.order.order_number)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты производства. Используйте ГГГГ-ММ-ДД")

    return RedirectResponse(url=f"/operator/session/{session_id}", status_code=303)

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
            message=f"Заказ #{session.order.order_number} полностью упакован ({session.order.total_applied}/{session.order.quantity}). Отделу маркировки необходимо сделать отчет о нанесении."
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
            message=f"Заказ #{session.order.order_number} полностью упакован. Отделу маркировки необходимо сделать отчет о нанесении."
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
