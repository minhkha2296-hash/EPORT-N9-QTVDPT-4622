import enum
import uuid
from datetime import datetime, timezone
from typing import Generator

from fastapi import Depends, FastAPI, HTTPException, Path, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from models import (
    AuditLog,
    Base,
    Container,
    ContainerStatus,
    Order,
    PaymentStatus,
    ServiceType,
    SessionLocal,
    Tariff,
    User,
    UserRole,
    Vessel,
    engine,
)
from schemas import (
    ContainerLookupResponse,
    GateCheckinRequest,
    GateCheckinResponse,
    OrderCreateRequest,
    OrderPayResponse,
    OrderResponse,
    VesselSummary,
)
from utils import generate_qr_base64, validate_iso6346

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ePort Enterprise API",
    description="Hệ thống Cảng Điện Tử chuẩn nghiệp vụ khai thác Container",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _normalize_dt(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _status_value(status_val: object) -> str:
    if isinstance(status_val, enum.Enum):
        return str(status_val.value)
    return str(status_val)


def _write_log(db: Session, actor: str, action: str, target: str, detail: str) -> None:
    db.add(AuditLog(actor=actor, action=action, target=target, detail=detail))


@app.get("/api/containers/{cntr_no}", response_model=ContainerLookupResponse)
def lookup_container(
    cntr_no: str = Path(..., min_length=1, max_length=20),
    db: Session = Depends(get_db),
) -> ContainerLookupResponse:
    normalized_no = cntr_no.strip().upper()
    is_valid = validate_iso6346(normalized_no)

    container = db.query(Container).filter(Container.cntr_no == normalized_no).first()
    if not container:
        return ContainerLookupResponse(
            cntr_no=normalized_no,
            is_iso6346_valid=is_valid,
            found_in_yard=False,
        )

    vessel_summary = VesselSummary.model_validate(container.vessel) if container.vessel else None

    return ContainerLookupResponse(
        cntr_no=container.cntr_no,
        is_iso6346_valid=is_valid,
        found_in_yard=True,
        id=container.id,
        size_type=container.size_type,
        status=container.status,
        customs_cleared=container.customs_cleared,
        do_expiry_date=container.do_expiry_date,
        yard_in_date=container.yard_in_date,
        yard_location=container.yard_location,
        vessel=vessel_summary,
    )
@app.post("/api/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreateRequest,
    db: Session = Depends(get_db),
) -> OrderResponse:
    now = datetime.now(timezone.utc)
    normalized_cntr_no = payload.cntr_no.strip().upper()
    normalized_truck_no = payload.truck_no.strip().upper()

    if not validate_iso6346(normalized_cntr_no):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Số container {normalized_cntr_no} không đúng chuẩn quốc tế ISO 6346 (sai check-digit hoặc định dạng).",
        )

    container = db.query(Container).filter(Container.cntr_no == normalized_cntr_no).first()
    if not container:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Container {normalized_cntr_no} không tồn tại trên hệ thống bãi cảng.",
        )

    existing_active_order = (
        db.query(Order)
        .filter(
            Order.container_id == container.id,
            Order.payment_status.in_([PaymentStatus.UNPAID, PaymentStatus.PAID]),
        )
        .first()
    )
    if existing_active_order:
    already_delivered = (
        db.query(Order)
        .filter(
            Order.container_id == container.id,
            Order.service_type == ServiceType.GIAO_NHAP,
            Order.payment_status == PaymentStatus.COMPLETED,
        )
        .first()
    )
    if already_delivered:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Container {normalized_cntr_no} đã rời khỏi cảng theo phiếu {already_delivered.eir_no} ({already_delivered.order_code}).",
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Container {normalized_cntr_no} đang có lệnh {existing_active_order.order_code} ({existing_active_order.payment_status.value}) chưa hoàn tất.",
        )

    if payload.service_type == ServiceType.GIAO_NHAP:
        if container.status != ContainerStatus.IMPORT_FULL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sai nghiệp vụ: Container {normalized_cntr_no} đang ở trạng thái {container.status.value}, không thể tạo lệnh GIAO_NHAP.",
            )
        if not container.customs_cleared:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Container {normalized_cntr_no} chưa được Hải quan thanh lý thông quan (VNACCS).",
            )
        expiry_utc = _normalize_dt(container.do_expiry_date)
        if expiry_utc is None or now > expiry_utc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lệnh giao hàng điện tử (eD/O) của container {normalized_cntr_no} đã hết hạn.",
            )

    elif payload.service_type == ServiceType.HA_XUAT:
        if container.status != ContainerStatus.EXPORT_FULL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sai nghiệp vụ: Container {normalized_cntr_no} đang ở trạng thái {container.status.value}, không thể tạo lệnh HA_XUAT.",
            )
        vessel = container.vessel or db.query(Vessel).order_by(Vessel.id.desc()).first()
        if not vessel:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không tìm thấy lịch tàu (Vessel Schedule) cho container hàng xuất.",
            )
        closing_utc = _normalize_dt(vessel.closing_time)
        if closing_utc is None or now >= closing_utc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Đã quá giờ cắt máng (Closing Time: {vessel.closing_time.strftime('%d/%m/%Y %H:%M')}) của tàu {vessel.vessel_name}.",
            )

    elif payload.service_type in (ServiceType.CAP_RONG, ServiceType.TRA_RONG):
        if container.status != ContainerStatus.EMPTY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sai nghiệp vụ: Container {normalized_cntr_no} đang có hàng ({container.status.value}), không thể làm lệnh rỗng.",
            )

    user = (
        db.query(User).filter(User.id == payload.user_id).first()
        if payload.user_id
        else db.query(User).filter(User.role == UserRole.CUSTOMER).first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không tìm thấy thông tin khách hàng.")

    tariff = (
        db.query(Tariff)
        .filter(Tariff.service_type == payload.service_type, Tariff.size_type == container.size_type)
        .first()
    )
    if not tariff:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chưa cấu hình biểu cước cho dịch vụ này.")

    yard_in_utc = _normalize_dt(container.yard_in_date) or now
    days_in_yard = max(0, (now - yard_in_utc).days)
    billable_storage_days = max(0, days_in_yard - tariff.free_days)
    storage_fee = billable_storage_days * tariff.storage_rate_per_day
    handling_fee = tariff.unit_price
    total_amount = round((handling_fee + storage_fee) * (1.0 + tariff.vat_rate), 2)

    order_code = f"ORD-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    qr_token = f"EPORT-{order_code}-{uuid.uuid4().hex[:8].upper()}"

    new_order = Order(
        order_code=order_code,
        service_type=payload.service_type,
        truck_no=normalized_truck_no,
        handling_fee=handling_fee,
        storage_fee=storage_fee,
        total_amount=total_amount,
        payment_status=PaymentStatus.UNPAID,
        qr_token=qr_token,
        created_at=now,
        user_id=user.id,
        container_id=container.id,
    )
    db.add(new_order)
    _write_log(
        db,
        actor=user.username,
        action="CREATE_ORDER",
        target=order_code,
        detail=f"Tạo lệnh {payload.service_type.value} cho cont {normalized_cntr_no}, xe {normalized_truck_no}",
    )
    db.commit()
    db.refresh(new_order)

    return OrderResponse(
        id=new_order.id,
        order_code=new_order.order_code,
        cntr_no=container.cntr_no,
        service_type=new_order.service_type,
        truck_no=new_order.truck_no,
        handling_fee=new_order.handling_fee,
        storage_fee=new_order.storage_fee,
        total_amount=new_order.total_amount,
        payment_status=_status_value(new_order.payment_status),
        qr_token=new_order.qr_token,
        created_at=new_order.created_at,
        user_id=new_order.user_id,
        container_id=new_order.container_id,
    )
@app.post("/api/orders/{order_id}/pay", response_model=OrderPayResponse)
def pay_order(
    order_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> OrderPayResponse:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lệnh làm hàng.")

    current_status = _status_value(order.payment_status)
    if current_status == "CANCELLED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lệnh đã bị hủy, không thể thanh toán.")
    if current_status == "COMPLETED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lệnh này đã hoàn tất qua cổng.")

    if current_status == "UNPAID":
        order.payment_status = PaymentStatus.PAID
        _write_log(
            db,
            actor="payment_gateway",
            action="PAY_ORDER",
            target=order.order_code,
            detail=f"Thanh toán thành công số tiền {order.total_amount:,.0f} VND",
        )
        db.commit()
        db.refresh(order)

    qr_payload = f"{order.qr_token}|ORDER:{order.order_code}|TRUCK:{order.truck_no}"
    qr_base64 = generate_qr_base64(qr_payload)

    return OrderPayResponse(
        order_id=order.id,
        order_code=order.order_code,
        payment_status=_status_value(order.payment_status),
        qr_token=order.qr_token,
        qr_base64=qr_base64,
        message="Thanh toán thành công! Mã QR eDO đã sẵn sàng để xe qua cổng Smart Gate.",
    )


@app.post("/api/gate/checkin", response_model=GateCheckinResponse)
def gate_checkin(
    payload: GateCheckinRequest,
    db: Session = Depends(get_db),
) -> GateCheckinResponse:
    now = datetime.now(timezone.utc)
    token = payload.qr_token.strip()
    order = db.query(Order).filter(Order.qr_token == token).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mã QR không hợp lệ hoặc không tồn tại.")

    current_status = _status_value(order.payment_status)
    if current_status == "UNPAID":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Lệnh {order.order_code} CHƯA THANH TOÁN.")
    if current_status == "CANCELLED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Lệnh {order.order_code} ĐÃ BỊ HỦY.")
    if current_status == "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CẢNH BÁO GIAN LẬN: Mã QR của lệnh {order.order_code} đã được sử dụng qua cổng trước đó!",
        )

    container = order.container
    if not container:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không tìm thấy dữ liệu container gắn với lệnh.")

    if order.service_type == ServiceType.GIAO_NHAP:
        if not container.customs_cleared:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"TỪ CHỐI TẠI CỔNG: Container {container.cntr_no} đã bị Hải quan khóa/hủy thông quan!",
            )
        expiry_utc = _normalize_dt(container.do_expiry_date)
        if expiry_utc is None or now > expiry_utc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"TỪ CHỐI TẠI CỔNG: Lệnh eD/O của container {container.cntr_no} đã hết hạn lúc xe tới cổng!",
            )

    eir_no = f"EIR-{now.strftime('%y%m%d')}-{order.id:05d}"
    order.payment_status = PaymentStatus.COMPLETED
    order.eir_no = eir_no
    order.checked_in_at = now

    _write_log(
        db,
        actor=payload.gate_operator,
        action="GATE_CHECKIN",
        target=order.order_code,
        detail=f"Xe {order.truck_no} qua cổng với cont {container.cntr_no}. Cấp phiếu {eir_no}",
    )
    db.commit()
    db.refresh(order)

    vessel_info = f"{container.vessel.vessel_name} ({container.vessel.voyage_no})" if container.vessel else "N/A"

    return GateCheckinResponse(
        order_id=order.id,
        order_code=order.order_code,
        eir_no=eir_no,
        cntr_no=container.cntr_no,
        size_type=container.size_type.value,
        service_type=order.service_type,
        truck_no=order.truck_no,
        yard_location=container.yard_location or "Bãi chỉ định",
        vessel_info=vessel_info,
        total_amount=order.total_amount,
        payment_status=_status_value(order.payment_status),
        checked_in_at=now,
        message=f"MỞ BARRIER THÀNH CÔNG! Đã cấp phiếu giao nhận {eir_no} cho xe {order.truck_no}.",
    )
