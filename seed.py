import hashlib
import random
from datetime import datetime, timedelta, timezone

from models import (
    AuditLog,
    Base,
    Container,
    ContainerStatus,
    Order,
    PaymentStatus,
    ServiceType,
    SessionLocal,
    SizeType,
    Tariff,
    User,
    UserRole,
    Vessel,
    engine,
)
from utils import calculate_iso6346_check_digit, validate_iso6346


def hash_password(raw_password: str) -> str:
    return hashlib.sha256(raw_password.encode("utf-8")).hexdigest()


def build_valid_iso6346(prefix_ten: str) -> str:
    cleaned = prefix_ten.strip().upper()
    check_digit = calculate_iso6346_check_digit(cleaned)
    return f"{cleaned}{check_digit}"


def seed_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    random.seed(2026)
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        # 1. Tài khoản hệ thống
        admin_user = User(
            username="admin_eport",
            full_name="Nguyễn Văn Quản Trị",
            email="admin@vntvt-port.vn",
            hashed_password=hash_password("Admin@123"),
            role=UserRole.ADMIN,
            company_name="Phòng Thương Vụ & Hải Quan Cảng VNTVT",
        )
        gate_user = User(
            username="gate_01",
            full_name="Trần Thị Cổng",
            email="gate01@vntvt-port.vn",
            hashed_password=hash_password("Gate@123"),
            role=UserRole.GATE,
            company_name="Đội Điều Hành Smart Gate VNTVT",
        )
        customer_user = User(
            username="cust_logistics",
            full_name="Lê Minh Khang",
            email="khang.le@logistics-vn.com",
            hashed_password=hash_password("Cust@123"),
            role=UserRole.CUSTOMER,
            company_name="Công Ty TNHH Logistics Phương Nam",
        )
        db.add_all([admin_user, gate_user, customer_user])
        db.flush()

        # 2. Lịch tàu (4 chuyến tàu đang làm hàng)
        vessels = [
            Vessel(vessel_name="MV SAIGON VOYAGER", voyage_no="V2611N", eta=now - timedelta(days=5), closing_time=now + timedelta(days=1, hours=6), port_code="VNTVT"),
            Vessel(vessel_name="MV MEKONG STAR", voyage_no="V2612S", eta=now + timedelta(days=1), closing_time=now + timedelta(days=3, hours=12), port_code="VNTVT"),
            Vessel(vessel_name="MV PACIFIC DRAGON", voyage_no="V2615E", eta=now - timedelta(days=2), closing_time=now + timedelta(days=2, hours=4), port_code="VNTVT"),
            Vessel(vessel_name="MV ORIENT EXPRESS", voyage_no="V2618W", eta=now + timedelta(days=2), closing_time=now + timedelta(days=4, hours=18), port_code="VNTVT"),
        ]
        db.add_all(vessels)
        db.flush()

        # 3. Biểu cước chuẩn
        tariffs_data = [
            Tariff(service_type=ServiceType.GIAO_NHAP, size_type=SizeType.GP_20, unit_price=1450000.0, storage_rate_per_day=250000.0, free_days=3, vat_rate=0.08),
            Tariff(service_type=ServiceType.GIAO_NHAP, size_type=SizeType.HC_40, unit_price=2250000.0, storage_rate_per_day=450000.0, free_days=3, vat_rate=0.08),
            Tariff(service_type=ServiceType.HA_XUAT, size_type=SizeType.GP_20, unit_price=1350000.0, storage_rate_per_day=200000.0, free_days=5, vat_rate=0.08),
            Tariff(service_type=ServiceType.HA_XUAT, size_type=SizeType.HC_40, unit_price=2100000.0, storage_rate_per_day=380000.0, free_days=5, vat_rate=0.08),
            Tariff(service_type=ServiceType.CAP_RONG, size_type=SizeType.GP_20, unit_price=950000.0, storage_rate_per_day=150000.0, free_days=5, vat_rate=0.08),
            Tariff(service_type=ServiceType.CAP_RONG, size_type=SizeType.HC_40, unit_price=1500000.0, storage_rate_per_day=280000.0, free_days=5, vat_rate=0.08),
            Tariff(service_type=ServiceType.TRA_RONG, size_type=SizeType.GP_20, unit_price=900000.0, storage_rate_per_day=150000.0, free_days=5, vat_rate=0.08),
            Tariff(service_type=ServiceType.TRA_RONG, size_type=SizeType.HC_40, unit_price=1400000.0, storage_rate_per_day=280000.0, free_days=5, vat_rate=0.08),
        ]
        db.add_all(tariffs_data)
        db.flush()

        # 4. Sinh 120 Container chuẩn ISO 6346 đa dạng nghiệp vụ
        prefixes = ["MSKU", "TCLU", "CMAU", "HLXU", "OOLU", "EMCU", "SEGU", "CAIU", "TRLU", "FSCU", "NYKU", "ONEU"]
        blocks = ["A1", "A2", "B1", "B2", "C1", "C2", "D1", "D2", "E1", "E2"]
        used_numbers = set()
        containers_objs = []

        # 5 container cố định đầu tiên để dễ nhớ khi demo
        fixed_samples = [
            ("MSKU123456", SizeType.GP_20, ContainerStatus.IMPORT_FULL, True, 5, 1, "A1-01-01", vessels[0].id),
            ("TCLU765432", SizeType.HC_40, ContainerStatus.IMPORT_FULL, True, 3, 5, "A1-01-02", vessels[0].id),
            ("HLXU889911", SizeType.HC_40, ContainerStatus.IMPORT_FULL, False, 4, 2, "B1-02-01", vessels[0].id),
            ("EMCU445566", SizeType.HC_40, ContainerStatus.EXPORT_FULL, True, None, 1, "D1-01-01", vessels[1].id),
            ("CAIU112233", SizeType.GP_20, ContainerStatus.EMPTY, True, None, 1, "E1-01-01", vessels[1].id),
        ]

        for p10, sz, st_val, cleared, do_days, yard_days, loc, v_id in fixed_samples:
            c_no = build_valid_iso6346(p10)
            used_numbers.add(c_no)
            containers_objs.append(
                Container(
                    cntr_no=c_no,
                    size_type=sz,
                    status=st_val,
                    customs_cleared=cleared,
                    do_expiry_date=(now + timedelta(days=do_days)) if do_days is not None else None,
                    yard_in_date=now - timedelta(days=yard_days),
                    yard_location=loc,
                    vessel_id=v_id,
                )
            )

        # Sinh ngẫu nhiên 115 container còn lại cho đủ 120 container
        while len(containers_objs) < 120:
            prefix = random.choice(prefixes)
            serial = f"{random.randint(100000, 999999)}"
            c_no = build_valid_iso6346(f"{prefix}{serial}")
            if c_no in used_numbers:
                continue
            used_numbers.add(c_no)

            idx = len(containers_objs)
            size_t = random.choice([SizeType.GP_20, SizeType.HC_40])
            block = blocks[idx % len(blocks)]
            bay = f"{(idx % 20) + 1:02d}"
            tier = f"{(idx % 4) + 1:02d}"
            location = f"{block}-{bay}-{tier}"
            vessel_obj = random.choice(vessels)
            days_in = random.randint(0, 7)

            # Chia đều: ~45% Hàng nhập, ~30% Hàng xuất, ~25% Cont rỗng
            if idx < 55:
                c_status = ContainerStatus.IMPORT_FULL
                is_cleared = random.random() < 0.75
                do_offset = random.choice([-2, -1, 2, 3, 5, 7])
                do_exp = now + timedelta(days=do_offset)
            elif idx < 90:
                c_status = ContainerStatus.EXPORT_FULL
                is_cleared = random.random() < 0.85
                do_exp = None
            else:
                c_status = ContainerStatus.EMPTY
                is_cleared = True
                do_exp = None

            containers_objs.append(
                Container(
                    cntr_no=c_no,
                    size_type=size_t,
                    status=c_status,
                    customs_cleared=is_cleared,
                    do_expiry_date=do_exp,
                    yard_in_date=now - timedelta(days=days_in),
                    yard_location=location,
                    vessel_id=vessel_obj.id,
                )
            )

        db.add_all(containers_objs)
        db.flush()

        # 5. Tạo sẵn 15 lệnh ePort mẫu ở đủ các trạng thái (UNPAID, PAID, COMPLETED)
        sample_trucks = ["51C-889.66", "50H-234.19", "51D-456.78", "60C-991.22", "61H-112.34", "51C-774.10"]
        orders_list = []
        for i in range(15):
            c_obj = containers_objs[i + 5]
            if c_obj.status == ContainerStatus.IMPORT_FULL and c_obj.customs_cleared:
                srv = ServiceType.GIAO_NHAP
            elif c_obj.status == ContainerStatus.EXPORT_FULL:
                srv = ServiceType.HA_XUAT
            elif c_obj.status == ContainerStatus.EMPTY:
                srv = random.choice([ServiceType.CAP_RONG, ServiceType.TRA_RONG])
            else:
                continue

            base_fee = 1450000.0 if c_obj.size_type == SizeType.GP_20 else 2250000.0
            p_status = random.choice([PaymentStatus.UNPAID, PaymentStatus.PAID, PaymentStatus.COMPLETED])
            o_code = f"ORD-20261125-{100 + i}"
            eir_code = f"EIR-261125-{100 + i:05d}" if p_status == PaymentStatus.COMPLETED else None

            orders_list.append(
                Order(
                    order_code=o_code,
                    eir_no=eir_code,
                    service_type=srv,
                    truck_no=random.choice(sample_trucks),
                    handling_fee=base_fee,
                    storage_fee=0.0,
                    total_amount=round(base_fee * 1.08, 2),
                    payment_status=p_status,
                    qr_token=f"EPORT-{o_code}-DEMO{i:02d}",
                    created_at=now - timedelta(hours=random.randint(1, 48)),
                    checked_in_at=(now - timedelta(minutes=random.randint(10, 120))) if p_status == PaymentStatus.COMPLETED else None,
                    user_id=customer_user.id,
                    container_id=c_obj.id,
                )
            )

        db.add_all(orders_list)
        db.add(
            AuditLog(
                actor="system",
                action="INIT_ENTERPRISE_DB",
                target="eport.db",
                detail=f"Khởi tạo thành công {len(containers_objs)} containers (10 Blocks) & {len(orders_list)} lệnh mẫu.",
            )
        )
        db.commit()
        print(f"Khoi tao thanh cong {len(containers_objs)} containers va {len(orders_list)} lenh mau!")


if __name__ == "__main__":
    seed_database()
