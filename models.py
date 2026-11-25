import enum
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

DATABASE_URL = "sqlite:///./eport.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"
    GATE = "GATE"


class SizeType(str, enum.Enum):
    GP_20 = "20GP"
    HC_40 = "40HC"


class ContainerStatus(str, enum.Enum):
    IMPORT_FULL = "IMPORT_FULL"
    EXPORT_FULL = "EXPORT_FULL"
    EMPTY = "EMPTY"


class ServiceType(str, enum.Enum):
    GIAO_NHAP = "GIAO_NHAP"
    HA_XUAT = "HA_XUAT"
    CAP_RONG = "CAP_RONG"
    TRA_RONG = "TRA_RONG"


class PaymentStatus(str, enum.Enum):
    UNPAID = "UNPAID"
    PAID = "PAID"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.CUSTOMER)
    company_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    orders: Mapped[List["Order"]] = relationship("Order", back_populates="customer")


class Vessel(Base):
    __tablename__ = "vessels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vessel_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    voyage_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    eta: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closing_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    port_code: Mapped[str] = mapped_column(String(20), default="VNCLI", nullable=False)

    containers: Mapped[List["Container"]] = relationship("Container", back_populates="vessel")


class Container(Base):
    __tablename__ = "containers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cntr_no: Mapped[str] = mapped_column(String(11), unique=True, nullable=False, index=True)
    size_type: Mapped[SizeType] = mapped_column(Enum(SizeType), nullable=False)
    status: Mapped[ContainerStatus] = mapped_column(Enum(ContainerStatus), nullable=False)
    customs_cleared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    do_expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    yard_in_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    yard_location: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    vessel_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vessels.id"), nullable=True)

    vessel: Mapped[Optional["Vessel"]] = relationship("Vessel", back_populates="containers")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="container")


class Tariff(Base):
    __tablename__ = "tariffs"
    __table_args__ = (
        UniqueConstraint("service_type", "size_type", name="uq_tariff_service_size"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    service_type: Mapped[ServiceType] = mapped_column(Enum(ServiceType), nullable=False)
    size_type: Mapped[SizeType] = mapped_column(Enum(SizeType), nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    storage_rate_per_day: Mapped[float] = mapped_column(Float, default=250000.0, nullable=False)
    free_days: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    vat_rate: Mapped[float] = mapped_column(Float, default=0.08, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="VND", nullable=False)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    eir_no: Mapped[Optional[str]] = mapped_column(String(30), unique=True, nullable=True)
    service_type: Mapped[ServiceType] = mapped_column(Enum(ServiceType), nullable=False)
    truck_no: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    handling_fee: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    storage_fee: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus),
        default=PaymentStatus.UNPAID,
        nullable=False,
    )
    qr_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    checked_in_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    container_id: Mapped[int] = mapped_column(ForeignKey("containers.id"), nullable=False)

    customer: Mapped["User"] = relationship("User", back_populates="orders")
    container: Mapped["Container"] = relationship("Container", back_populates="orders")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target: Mapped[str] = mapped_column(String(100), nullable=False)
    detail: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
