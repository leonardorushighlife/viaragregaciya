from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user, require_admin
from app.models.models import AppSetting, User

templates = Jinja2Templates(directory="templates")

settings_router = APIRouter()

@settings_router.get("/settings", response_class=HTMLResponse)
async def get_settings(
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    settings_records = db.query(AppSetting).all()
    settings_dict = {s.key: s.value for s in settings_records}
    all_users = db.query(User).all()

    return templates.TemplateResponse(request=request, name="settings/settings.html", context={
        "role": admin_user.role,
        "current_user": admin_user,
        "all_users": all_users,
        "settings_dict": settings_dict,
        "message": None
    })

@settings_router.post("/settings", response_class=HTMLResponse)
async def post_settings(
    request: Request,
    ip_facade: str = Form(""),
    ip_labeling: str = Form(""),
    ip_operator: str = Form(""),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    form_data = {
        "ip_facade": ip_facade,
        "ip_labeling": ip_labeling,
        "ip_operator": ip_operator
    }

    for key, val in form_data.items():
        setting = db.query(AppSetting).filter(AppSetting.key == key).first()
        if not setting:
            setting = AppSetting(section="network", key=key, value=val)
            db.add(setting)
        else:
            setting.value = val

    db.commit()

    settings_records = db.query(AppSetting).all()
    settings_dict = {s.key: s.value for s in settings_records}
    all_users = db.query(User).all()

    return templates.TemplateResponse(request=request, name="settings/settings.html", context={
        "role": admin_user.role,
        "current_user": admin_user,
        "all_users": all_users,
        "settings_dict": settings_dict,
        "message": "Настройки сохранены"
    })

@settings_router.get("/switch-user")
async def switch_user(user_id: int, redirect_url: str = "/"):
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie("user_id", str(user_id))
    return response
