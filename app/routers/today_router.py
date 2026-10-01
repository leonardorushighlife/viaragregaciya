from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.models import Order, OperatorSession, Task, User, OrderStatus

templates = Jinja2Templates(directory="templates")

today_router = APIRouter()

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

@today_router.get("/today", response_class=HTMLResponse)
async def today_summary(request: Request, db: Session = Depends(get_db)):
    current_user = get_user_for_request(request, db)
    today_date = date.today()

    # All sessions active or updated today
    all_sessions = db.query(OperatorSession).all()
    sessions_today = [
        s for s in all_sessions
        if (s.started_at and s.started_at.date() == today_date) or
           (s.finished_at and s.finished_at.date() == today_date) or
           (s.paused_at and s.paused_at.date() == today_date)
    ]

    applied_today = sum(s.applied_qty for s in sessions_today)

    # Orders active or created today or labeled today
    all_orders = db.query(Order).all()
    orders_today = [
        o for o in all_orders
        if (o.actual_labeling_date == today_date) or
           (o.created_at and o.created_at.date() == today_date) or
           (o.updated_at and o.updated_at.date() == today_date)
    ]

    target_qty_today = sum(o.quantity for o in orders_today) if orders_today else sum(o.quantity for o in all_orders)
    defect_qty_today = sum(o.defect_qty for o in orders_today) if orders_today else sum(o.defect_qty for o in all_orders)
    defect_percent = round((defect_qty_today / target_qty_today * 100), 1) if target_qty_today > 0 else 0.0

    # Operator specific
    my_sessions_today = [s for s in sessions_today if s.operator_id == current_user.id]
    my_applied_today = sum(s.applied_qty for s in my_sessions_today)
    my_time_seconds = sum(s.duration_seconds for s in my_sessions_today)

    all_users = db.query(User).all()

    return templates.TemplateResponse(request=request, name="today.html", context={
        "role": current_user.role,
        "current_user": current_user,
        "all_users": all_users,
        "today_date": today_date,
        "applied_today": applied_today,
        "target_qty_today": target_qty_today,
        "defect_qty_today": defect_qty_today,
        "defect_percent": defect_percent,
        "orders_today": orders_today if orders_today else all_orders,
        "sessions_today": sessions_today,
        "my_sessions_today": my_sessions_today,
        "my_applied_today": my_applied_today,
        "my_time_seconds": my_time_seconds
    })
