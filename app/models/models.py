from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Date, ForeignKey, Float, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base

class OrderStatus(str, enum.Enum):
    DRAFT = "DRAFT"                      # Черновик фасада
    SENT_TO_LABELING = "SENT_TO_LABELING"# Передано в отдел маркировки
    CODES_REQUESTED = "CODES_REQUESTED"  # Запрошены коды в ЧЗ
    CODES_PRINTED = "CODES_PRINTED"      # Коды напечатаны
    IN_PACKAGING = "IN_PACKAGING"        # Выполняется оператором
    PACKAGED = "PACKAGED"                # Упаковано оператором
    COMPLETED = "COMPLETED"              # Отчет сдан, заказ закрыт
    CANCELLED = "CANCELLED"              # Отменен

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
    role = Column(String(50), default="operator")  # "admin", "operator", "facade", "labeling"
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    sessions = relationship("OperatorSession", back_populates="operator", cascade="all, delete-orphan")

class AppSetting(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    section = Column(String(50), default="network")  # network / other
    key = Column(String(50), unique=True, index=True, nullable=False)  # ip_facade, ip_labeling, ip_operator
    value = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    official_name = Column(String(255), nullable=False)
    facade_name = Column(String(255), nullable=True)     # Внутреннее имя для фасада
    labeling_name = Column(String(255), nullable=True)   # Внутреннее имя для маркировки
    gtin = Column(String(14), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("Order", back_populates="product")

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, index=True, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    shipment_date = Column(Date, nullable=False)
    status = Column(String(50), default=OrderStatus.DRAFT.value)
    notes = Column(Text, nullable=True)
    defect_qty = Column(Integer, default=0, nullable=False)
    actual_labeling_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = relationship("Product", back_populates="orders")
    tasks = relationship("Task", back_populates="order", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="order", cascade="all, delete-orphan")
    sessions = relationship("OperatorSession", back_populates="order", cascade="all, delete-orphan")

    @property
    def total_applied(self) -> int:
        if not self.sessions:
            return 0
        return sum(s.applied_qty for s in self.sessions)

    @property
    def remaining_codes(self) -> int:
        return max(0, self.quantity - self.total_applied)

    @property
    def operators_count(self) -> int:
        if not self.sessions:
            return 0
        return len({s.operator_id for s in self.sessions})

    @property
    def total_execution_time(self) -> float:
        if not self.sessions:
            return 0.0
        return sum(s.duration_seconds for s in self.sessions)

    @property
    def average_session_time(self) -> float:
        finished_sessions = [s for s in self.sessions if s.finished_at is not None or s.status == "completed"]
        if not finished_sessions:
            return 0.0
        return sum(s.duration_seconds for s in finished_sessions) / len(finished_sessions)

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    quantity_target = Column(Integer, nullable=False)
    status = Column(String(50), default="pending")  # pending / in_progress / completed
    actual_started_at = Column(DateTime, nullable=True)
    actual_completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="tasks")

    @property
    def total_applied(self) -> int:
        if not self.order or not self.order.sessions:
            return 0
        return sum(s.applied_qty for s in self.order.sessions)

    @property
    def remaining_codes(self) -> int:
        if not self.order:
            return 0
        return self.order.remaining_codes

    @property
    def operators_count(self) -> int:
        if not self.order or not self.order.sessions:
            return 0
        return len({s.operator_id for s in self.order.sessions})

class OperatorSession(Base):
    __tablename__ = "operator_sessions"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    applied_qty = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    paused_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="running")  # running / paused / completed

    order = relationship("Order", back_populates="sessions")
    operator = relationship("User", back_populates="sessions")

    @property
    def duration_seconds(self) -> float:
        end_time = self.finished_at or self.paused_at or datetime.utcnow()
        return max(0.0, (end_time - self.started_at).total_seconds())

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String(50), default="ALL")  # FACADE, LABELING, OPERATOR, ALL
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    total_produced = Column(Integer, nullable=False)
    stickers_used = Column(Integer, nullable=False)
    stickers_wasted = Column(Integer, default=0)
    submitted_by = Column(String(100), default="Отдел маркировки")
    submitted_at = Column(DateTime, default=datetime.utcnow)
    comments = Column(Text, nullable=True)

    order = relationship("Order", back_populates="reports")
