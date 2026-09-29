from fastapi import Request, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.models.models import User

ADMIN_PASSWORD = "10072025"

def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    user_id = request.cookies.get("user_id") or request.query_params.get("user_id") or request.headers.get("X-User-ID")
    if user_id:
        try:
            user = db.get(User, int(user_id))
            if user:
                return user
        except ValueError:
            pass
    username = request.query_params.get("username")
    if username:
        user = db.query(User).filter(User.username == username).first()
        if user:
            return user
    return None

def require_admin(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    # Check for admin user or password provided in query/form
    provided_password = request.query_params.get("admin_password") or request.cookies.get("admin_password")

    if not current_user or not current_user.is_admin:
        # If user is not logged in as admin, check if correct admin password was supplied
        if provided_password != ADMIN_PASSWORD:
            raise HTTPException(status_code=403, detail="Доступ запрещен. Требуются права администратора (пароль: 10072025).")
        # Find or use admin user
        admin = db.query(User).filter(User.is_admin == True).first()
        if admin:
            return admin

    return current_user
