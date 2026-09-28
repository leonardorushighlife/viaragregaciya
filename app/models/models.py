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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = relationship("Product", back_populates="orders")
    tasks = relationship("Task", back_populates="order", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="order", cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    operator_name = Column(String(100), nullable=True)
    quantity_target = Column(Integer, nullable=False)
    quantity_completed = Column(Integer, default=0)
    remaining_stickers = Column(Integer, default=0)
    status = Column(String(50), default="PENDING") # PENDING, IN_PROGRESS, FINISHED
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    is_locked = Column(Boolean, default=False)

    order = relationship("Order", back_populates="tasks")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String(50), default="ALL") # FACADE, LABELING, OPERATOR, ALL
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
