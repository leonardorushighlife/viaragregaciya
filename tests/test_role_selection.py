import pytest
from httpx import AsyncClient, ASGITransport
from app.core.database import Base, engine, SessionLocal
from app.models.models import User
from main import app

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

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

    db.commit()
    db.close()
    yield

@pytest.mark.asyncio
async def test_role_selection_and_persistence():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Root redirect to /select-role when no cookie
        resp = await ac.get("/", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/select-role"

        # 2. Select Operator 2
        resp = await ac.post("/select-role", data={"role": "operator", "operator_username": "op2"}, follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/operator"
        cookies = resp.cookies

        # 3. Accessing / now auto redirects to /operator
        resp = await ac.get("/", cookies=cookies, follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/operator"

        # 4. Logout clears cookies and returns to /select-role
        resp = await ac.get("/logout", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/select-role"

        # 5. Incorrect admin password shows error
        resp = await ac.post("/select-role", data={"role": "admin", "admin_password": "wrong"}, follow_redirects=True)
        assert resp.status_code == 200
        assert "Неверный пароль администратора" in resp.text

        # 6. Correct admin password logs in
        resp = await ac.post("/select-role", data={"role": "admin", "admin_password": "10072025"}, follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/settings"
