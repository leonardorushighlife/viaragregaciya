from fastapi import Request, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.models.models import User

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
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    if not current_user or not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Доступ запрещен. Требуются права администратора.")
    return current_user
