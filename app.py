import os
from PIL import Image
import base64
import io
import threading
import time
from fpdf import FPDF
from datetime import datetime, timedelta, timezone

VN_TZ = timezone(timedelta(hours=7))

from typing import Any, Dict, List, Optional

import requests
import streamlit as st

from models import (
    AuditLog,
    Base,
    Container,
    Order,
    ServiceType,
    SessionLocal,
    SizeType,
    engine,
)
from utils import generate_qr_base64

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"


def ensure_db_ready() -> None:
    Base.metadata.create_all(bind=engine)

@st.cache_data
def get_transparent_logo_b64(img_path: str = "logo.jpg") -> str:
    if not os.path.exists(img_path):
        return ""
    img = Image.open(img_path).convert("RGBA")
    datas = img.getdata()
    new_data = []
    for r, g, b, a in datas:
        # Biến các điểm ảnh nền trắng/xám nhạt thành trong suốt
        if r > 235 and g > 235 and b > 235:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append((r, g, b, a))
    img.putdata(new_data)
    img.save("logo_transparent.png", "PNG")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def inject_custom_css() -> None:
    logo_b64 = get_transparent_logo_b64("logo.jpg")
    logo_bg_css = (
        f"background-image: url('data:image/png;base64,{logo_b64}');"
        f"background-size: 30px 30px; background-repeat: no-repeat; background-position: 10px center;"
        f"padding-left: 46px;"
        if logo_b64
        else "padding-left: 14px;"
    )

    st.markdown(
        f"""
        <style>
        html, body, [class*="css"] {{ font-family: 'Segoe UI', Arial, sans-serif; }}
        .stApp {{ background-color: #f1f5f9; }}

        /* 1. TOP HEADER BAR TỰ CO GIÃN KHÔNG ĐÈ NÚT DEPLOY */
        header[data-testid="stHeader"] {{
            background: rgba(255, 255, 255, 0.96) !important;
            backdrop-filter: blur(8px);
            border-bottom: 1px solid #cbd5e1 !important;
            height: 3.5rem !important;
        }}
        header[data-testid="stHeader"]::before {{
            content: "VNTVT SMART PORT";
            font-family: 'Segoe UI', Arial, sans-serif !important;
            position: absolute;
            left: 3.5rem;
            top: 50%;
            transform: translateY(-50%);
            font-size: 13px;
            font-weight: 800;
            color: #0b132b;
            background-color: #f0f9ff;
            border: 1px solid #bae6fd;
            padding-top: 5px;
            padding-bottom: 5px;
            padding-right: 14px;
            border-radius: 999px;
            white-space: nowrap;
            max-width: 52vw;
            overflow: hidden;
            text-overflow: ellipsis;
            {logo_bg_css}
        }}
        /* Làm sáng rõ nút thu gọn (<<) ở góc trên thanh Sidebar */
        section[data-testid="stSidebar"] button[kind="header"],
        section[data-testid="stSidebar"] button[data-testid="stSidebarCollapseButton"],
        section[data-testid="stSidebar"] div[data-testid="stSidebarHeader"] button {{
            background-color: #1e293b !important;
            border: 1.5px solid #38bdf8 !important;
            border-radius: 8px !important;
            opacity: 1 !important;
        }}
        section[data-testid="stSidebar"] button[kind="header"] svg,
        section[data-testid="stSidebar"] button[data-testid="stSidebarCollapseButton"] svg,
        section[data-testid="stSidebar"] div[data-testid="stSidebarHeader"] button svg,
        section[data-testid="stSidebar"] div[data-testid="stSidebarHeader"] button span {{
            color: #38bdf8 !important;
            fill: #38bdf8 !important;
        }}
        section[data-testid="stSidebar"] div[data-testid="stSidebarHeader"] button:hover {{
            background-color: #0284c7 !important;
        }}

        /* 2. SIDEBAR DARK MARITIME THEME */
        section[data-testid="stSidebar"] {{
            background-color: #0b132b !important;
            border-right: 1px solid #1e293b;
        }}
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] .stMarkdown {{
            color: #f8fafc !important;
        }}
        section[data-testid="stSidebar"] div[data-baseweb="select"] > div,
        section[data-testid="stSidebar"] input {{
            background-color: #1c2541 !important;
            border-color: #3a506b !important;
            color: #ffffff !important;
        }}
        section[data-testid="stSidebar"] div[data-baseweb="select"] span {{ color: #ffffff !important; }}
        section[data-testid="stSidebar"] details {{
            background-color: #131c38 !important;
            border: 1px solid #2b3a67 !important;
            border-radius: 8px;
        }}
        section[data-testid="stSidebar"] summary {{
            background-color: #1c2541 !important;
            color: #ffffff !important;
            border-radius: 8px;
        }}
        section[data-testid="stSidebar"] code {{
            background-color: #1e293b !important;
            color: #38bdf8 !important;
            font-weight: 700;
        }}

        /* 3. BANNER, THẺ KPI & NÚT BẤM CHÍNH */
        .maritime-banner {{
            background: linear-gradient(120deg, #0b132b 0%, #1c2541 55%, #0284c7 100%);
            color: white;
            padding: 22px 28px;
            border-radius: 14px;
            margin-bottom: 22px;
            box-shadow: 0 10px 25px -5px rgba(11, 19, 43, 0.25);
            border-left: 6px solid #38bdf8;
        }}
        .maritime-banner h1 {{ margin: 0; font-size: 22px; font-weight: 800; color: #ffffff; }}
        .maritime-banner p {{ margin: 6px 0 0 0; font-size: 13.5px; color: #cbd5e1; }}

        div[data-testid="metric-container"] {{
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-top: 4px solid #0284c7;
            padding: 16px 20px;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        }}

        button[kind="primary"], button[data-testid="baseButton-primary"], button[data-testid="stBaseButton-primary"] {{
            background: linear-gradient(135deg, #0284c7 0%, #1d4ed8 100%) !important;
            border: none !important;
            color: #ffffff !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_yard_map() -> None:
    now = datetime.now(VN_TZ)
    col_f1, col_f2, col_f3 = st.columns([1.2, 1.5, 2.0])
    with col_f1:
        block_filter = st.selectbox(
            "🏗️ Khu vực bãi (Yard Block):",
            options=["Tất cả Block (A - E)", "Block A", "Block B", "Block C", "Block D", "Block E"],
            key="yard_block_filter",
        )
    with col_f2:
        status_filter = st.selectbox(
            "🚦 Trạng thái khai thác:",
            options=["Tất cả trạng thái", "✅ Sẵn sàng giao/hạ", "🔒 Chờ Hải quan", "⚠️ Hết hạn eD/O"],
            key="yard_status_filter",
        )
    with col_f3:
        search_cntr = st.text_input("🔎 Tìm nhanh số Container:", placeholder="Nhập 4 chữ cái hoặc số (VD: MSKU, 7654...)", key="yard_search_cntr").strip().upper()

    with SessionLocal() as db:
        containers = db.query(Container).order_by(Container.yard_location.asc()).all()

    cards = []
    for c in containers:
        loc = c.yard_location or ""
        if block_filter != "Tất cả Block (A - E)":
            target_letter = block_filter.split(" ")[1]
            if not loc.startswith(target_letter):
                continue

        if search_cntr and search_cntr not in c.cntr_no:
            continue

        expiry = c.do_expiry_date
        if expiry is not None and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)

        if not c.customs_cleared:
            bg, border, badge_bg, badge_fg, label = "#fff1f2", "#f43f5e", "#ffe4e6", "#be123c", "🔒 Chờ Hải quan"
        elif c.status.value == "IMPORT_FULL" and (expiry is None or now > expiry):
            bg, border, badge_bg, badge_fg, label = "#fffbeb", "#f59e0b", "#fef3c7", "#b45309", "⚠️ Hết hạn eD/O"
        else:
            bg, border, badge_bg, badge_fg, label = "#f0fdf4", "#10b981", "#dcfce7", "#15803d", "✅ Sẵn sàng giao/hạ"

        if status_filter != "Tất cả trạng thái" and label != status_filter:
            continue

        card = (
            f'<div style="background:{bg};border:1px solid {border};border-top:4px solid {border};'
            f'border-radius:8px;padding:8px 10px;width:172px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">'
            f'<div style="display:flex;justify-content:space-between;font-size:10.5px;color:#475569;font-weight:700;">'
            f'<span>📍 {loc}</span><span>{c.size_type.value}</span></div>'
            f'<div style="font-size:13.5px;font-weight:800;color:#0f172a;margin:3px 0;letter-spacing:0.3px;">{c.cntr_no}</div>'
            f'<div style="font-size:10.5px;color:#334155;margin-bottom:4px;">{c.status.value}</div>'
            f'<span style="background:{badge_bg};color:{badge_fg};padding:2px 6px;border-radius:4px;font-size:10px;font-weight:700;">{label}</span>'
            f'</div>'
        )
        cards.append(card)

    st.caption(f"Đang hiển thị **{len(cards)}** / 120 container phù hợp bộ lọc (tối đa 30 ô tiêu biểu trên lưới):")
    display_cards = cards[:30]
    html = f'<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:15px;">{"".join(display_cards)}</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_yard_map() -> None:
    now = datetime.now(VN_TZ)
    with SessionLocal() as db:
        containers = db.query(Container).order_by(Container.yard_location.asc()).all()

    cards = []
    for c in containers:
        expiry = c.do_expiry_date
        if expiry is not None and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)

        if not c.customs_cleared:
            bg, border, label = "#fef2f2", "#ef4444", "🔒 Chờ Hải quan"
        elif c.status.value == "IMPORT_FULL" and (expiry is None or now > expiry):
            bg, border, label = "#fffbeb", "#f59e0b", "⚠️ Hết hạn eD/O"
        else:
            bg, border, label = "#f0fdf4", "#22c55e", "✅ Sẵn sàng giao/hạ"

        card = (
            f'<div style="background:{bg};border:1px solid {border};border-left:5px solid {border};'
            f'border-radius:8px;padding:10px 12px;min-width:175px;">'
            f'<div style="font-size:11px;color:#475569;font-weight:600;">📍 Vị trí: {c.yard_location}</div>'
            f'<div style="font-size:14px;font-weight:700;color:#0f172a;margin:3px 0;">{c.cntr_no}</div>'
            f'<div style="font-size:11px;color:#334155;">{c.size_type.value} • {c.status.value}</div>'
            f'<div style="font-size:11px;font-weight:600;margin-top:4px;">{label}</div>'
            f'</div>'
        )
        cards.append(card)

    html = f'<div style="display:flex;flex-wrap:wrap;gap:12px;margin-bottom:15px;">{"".join(cards)}</div>'
    st.markdown(html, unsafe_allow_html=True)

def render_order_stepper(status_str: str) -> None:
    step = 1
    if status_str == "UNPAID":
        step = 2
    elif status_str == "PAID":
        step = 3
    elif status_str == "COMPLETED":
        step = 4

    steps = [
        ("1", "Khai báo & Hải quan"),
        ("2", "Chờ thanh toán"),
        ("3", "Đã cấp mã QR eDO"),
        ("4", "Đã qua cổng (EIR)"),
    ]
    items_html = []
    for idx, (num, label) in enumerate(steps, start=1):
        active = idx <= step
        bg = "#1d4ed8" if active else "#e2e8f0"
        fg = "#ffffff" if active else "#64748b"
        text_color = "#0f172a" if active else "#94a3b8"
        weight = "700" if active else "500"
        check = "✓" if idx < step or step == 4 else num
        items_html.append(
            f'<div style="flex:1;text-align:center;">'
            f'<div style="width:30px;height:30px;line-height:30px;border-radius:50%;background:{bg};color:{fg};'
            f'margin:0 auto 6px auto;font-weight:700;font-size:13px;">{check}</div>'
            f'<div style="font-size:12px;color:{text_color};font-weight:{weight};">{label}</div>'
            f'</div>'
        )
    html = (
        f'<div style="display:flex;justify-content:space-between;background:#ffffff;padding:15px 10px;'
        f'border-radius:10px;border:1px solid #e2e8f0;margin:12px 0;">{"".join(items_html)}</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_svg_analytics() -> None:
    with SessionLocal() as db:
        containers = db.query(Container).all()
        orders = db.query(Order).all()

    import_cnt = sum(1 for c in containers if c.status.value == "IMPORT_FULL")
    export_cnt = sum(1 for c in containers if c.status.value == "EXPORT_FULL")
    empty_cnt = sum(1 for c in containers if c.status.value == "EMPTY")

    unpaid_cnt = sum(1 for o in orders if str(o.payment_status.value) == "UNPAID")
    paid_cnt = sum(1 for o in orders if str(o.payment_status.value) == "PAID")
    done_cnt = sum(1 for o in orders if str(o.payment_status.value) == "COMPLETED")

    max_c = max(import_cnt, export_cnt, empty_cnt, 1)
    h_imp = int((import_cnt / max_c) * 110)
    h_exp = int((export_cnt / max_c) * 110)
    h_emp = int((empty_cnt / max_c) * 110)

    chart_html = f"""
    <div style="display:flex;gap:20px;flex-wrap:wrap;margin:15px 0;">
        <div style="flex:1;min-width:280px;background:#ffffff;padding:18px;border-radius:12px;border:1px solid #e2e8f0;box-shadow:0 2px 6px rgba(0,0,0,0.03);">
            <div style="font-weight:700;color:#0f172a;margin-bottom:10px;font-size:15px;">📦 Cơ cấu Tồn bãi theo Trạng thái (Containers)</div>
            <svg width="100%" height="150" viewBox="0 0 300 150">
                <rect x="35" y="{125-h_imp}" width="45" height="{h_imp}" rx="6" fill="#1d4ed8"/>
                <text x="57" y="{118-h_imp}" text-anchor="middle" font-size="12" font-weight="bold" fill="#1e293b">{import_cnt}</text>
                <text x="57" y="143" text-anchor="middle" font-size="11" fill="#475569">Hàng Nhập</text>
                <rect x="125" y="{125-h_exp}" width="45" height="{h_exp}" rx="6" fill="#0ea5e9"/>
                <text x="147" y="{118-h_exp}" text-anchor="middle" font-size="12" font-weight="bold" fill="#1e293b">{export_cnt}</text>
                <text x="147" y="143" text-anchor="middle" font-size="11" fill="#475569">Hàng Xuất</text>
                <rect x="215" y="{125-h_emp}" width="45" height="{h_emp}" rx="6" fill="#64748b"/>
                <text x="237" y="{118-h_emp}" text-anchor="middle" font-size="12" font-weight="bold" fill="#1e293b">{empty_cnt}</text>
                <text x="237" y="143" text-anchor="middle" font-size="11" fill="#475569">Cont Rỗng</text>
            </svg>
        </div>
        <div style="flex:1;min-width:280px;background:#ffffff;padding:18px;border-radius:12px;border:1px solid #e2e8f0;box-shadow:0 2px 6px rgba(0,0,0,0.03);">
            <div style="font-weight:700;color:#0f172a;margin-bottom:12px;font-size:15px;">💳 Tiến độ Xử lý Lệnh ePort</div>
            <div style="margin-bottom:10px;font-size:13px;">Chờ thanh toán (UNPAID): <b>{unpaid_cnt} lệnh</b>
                <div style="background:#f1f5f9;height:10px;border-radius:5px;margin-top:4px;"><div style="background:#f59e0b;width:{min(100, unpaid_cnt*25)}%;height:10px;border-radius:5px;"></div></div>
            </div>
            <div style="margin-bottom:10px;font-size:13px;">Đã thanh toán (PAID - Chờ qua cổng): <b>{paid_cnt} lệnh</b>
                <div style="background:#f1f5f9;height:10px;border-radius:5px;margin-top:4px;"><div style="background:#3b82f6;width:{min(100, paid_cnt*25)}%;height:10px;border-radius:5px;"></div></div>
            </div>
            <div style="font-size:13px;">Hoàn tất qua cổng (COMPLETED): <b>{done_cnt} lệnh</b>
                <div style="background:#f1f5f9;height:10px;border-radius:5px;margin-top:4px;"><div style="background:#10b981;width:{min(100, done_cnt*25)}%;height:10px;border-radius:5px;"></div></div>
            </div>
        </div>
    </div>
    """
    st.markdown(chart_html, unsafe_allow_html=True)


def render_gate_led_board(is_open: bool, truck_no: str = "---", eir_no: str = "---") -> None:
    led_color = "#22c55e" if is_open else "#ef4444"
    status_text = "BARRIER OPEN — MỜI XE QUA LÀN GATE-01" if is_open else "BARRIER CLOSED — ĐANG CHỜ QUÉT MÃ QR eDO"
    html = (
        f'<div style="background:#0f172a;color:#f8fafc;padding:18px 22px;border-radius:12px;'
        f'border:2px solid {led_color};margin-bottom:16px;font-family:monospace;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span style="font-size:13px;color:#94a3b8;">LANE: SMART-GATE-01 | VNTVT PORT</span>'
        f'<span style="background:{led_color};color:#0f172a;padding:3px 10px;border-radius:4px;font-weight:bold;font-size:12px;">{"ONLINE • ACTIVE" if is_open else "STANDBY"}</span>'
        f'</div>'
        f'<div style="font-size:20px;font-weight:bold;color:{led_color};margin:10px 0;letter-spacing:1px;">● {status_text}</div>'
        f'<div style="font-size:13px;color:#cbd5e1;">BIỂN SỐ XE: <b>{truck_no}</b> &nbsp;|&nbsp; SỐ PHIẾU EIR: <b>{eir_no}</b></div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def format_vnd(amount: float) -> str:
    return f"{amount:,.0f} VND"


def format_dt(dt: Optional[datetime]) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")

def render_html_table(data_list: List[Dict[str, Any]]) -> None:
    if not data_list:
        return
    first_row = next(iter(data_list))
    headers = "".join(
        f"<th style='text-align:left;padding:10px 12px;background-color:#e2e8f0;color:#0f172a;border-bottom:2px solid #cbd5e1;font-size:12.5px;white-space:nowrap;'>{k}</th>"
        for k in first_row.keys()
    )
    rows = "".join(
        "<tr style='background-color:#ffffff;border-bottom:1px solid #e2e8f0;'>"
        + "".join(f"<td style='padding:9px 12px;font-size:13px;color:#1e293b;vertical-align:middle;'>{v}</td>" for v in row.values())
        + "</tr>"
        for row in data_list
    )
    st.markdown(
        f"<div style='overflow-x:auto;border-radius:10px;border:1px solid #cbd5e1;box-shadow:0 2px 5px rgba(0,0,0,0.03);margin-bottom:14px;'>"
        f"<table style='width:100%;border-collapse:collapse;'><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table></div>",
        unsafe_allow_html=True,
    )

def call_api(
    base_url: str,
    method: str,
    path: str,
    json_payload: Optional[Dict[str, Any]] = None,
    timeout: int = 10,
) -> tuple[bool, int, Dict[str, Any]]:
    url = f"{base_url.rstrip('/')}{path}"
    try:
        response = requests.request(method=method.upper(), url=url, json=json_payload, timeout=timeout)
        try:
            data = response.json()
        except ValueError:
            data = {"detail": response.text or "Phản hồi không phải JSON."}

        if 200 <= response.status_code < 300:
            return True, response.status_code, data
        return False, response.status_code, data
    except requests.ConnectionError:
        return False, 0, {"detail": f"Không thể kết nối Backend tại {base_url}."}
    except Exception as exc:
        return False, 0, {"detail": f"Lỗi: {exc}"}


def get_dashboard_kpis() -> Dict[str, Any]:
    with SessionLocal() as db:
        containers = db.query(Container).all()
        orders = db.query(Order).all()

        total_teu = sum(2 if c.size_type == SizeType.HC_40 else 1 for c in containers)
        cleared_count = sum(1 for c in containers if c.customs_cleared)
        clearance_rate = (cleared_count / len(containers) * 100) if containers else 0.0

        paid_orders = [
            o for o in orders
            if (o.payment_status.value if hasattr(o.payment_status, "value") else str(o.payment_status)) in ("PAID", "COMPLETED")
        ]
        total_revenue = sum(o.total_amount for o in paid_orders)
        completed_gates = sum(
            1 for o in orders
            if (o.payment_status.value if hasattr(o.payment_status, "value") else str(o.payment_status)) == "COMPLETED"
        )

        return {
            "total_containers": len(containers),
            "total_teu": total_teu,
            "clearance_rate": clearance_rate,
            "total_revenue": total_revenue,
            "completed_gates": completed_gates,
        }
def fetch_containers_from_db() -> List[Dict[str, Any]]:
    now = datetime.now(VN_TZ)
    rows: List[Dict[str, Any]] = []
    with SessionLocal() as db:
        containers = db.query(Container).order_by(Container.id.asc()).all()
        for c in containers:
            expiry = c.do_expiry_date
            if expiry is not None and expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)

            yard_in = c.yard_in_date
            if yard_in.tzinfo is None:
                yard_in = yard_in.replace(tzinfo=timezone.utc)
            days_in_yard = max(0, (now - yard_in).days)

            if c.status.value == "IMPORT_FULL":
                do_status = "Hết hạn eD/O" if (expiry is None or now > expiry) else "Còn hạn eD/O"
            else:
                do_status = "Không áp dụng"

            vessel_label = f"{c.vessel.vessel_name} ({c.vessel.voyage_no})" if c.vessel else "—"

            rows.append(
                {
                    "Số Container": f"<b>{c.cntr_no}</b>",
                    "Kích cỡ": c.size_type.value,
                    "Trạng thái": c.status.value,
                    "Lưu bãi": f"{days_in_yard} ngày",
                    "Hải quan (VNACCS)": "✅ Thông quan" if c.customs_cleared else "❌ Chưa thông quan",
                    "Tình trạng eD/O": do_status,
                    "Vị trí bãi": c.yard_location or "—",
                    "Tàu / Chuyến": vessel_label,
                }
            )
    return rows


def fetch_orders_from_db() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with SessionLocal() as db:
        orders = db.query(Order).order_by(Order.id.desc()).all()
        for o in orders:
            cntr_no = o.container.cntr_no if o.container else "—"
            status_val = o.payment_status.value if hasattr(o.payment_status, "value") else str(o.payment_status)
            rows.append(
                {
                    "Mã lệnh": f"<b>{o.order_code}</b>",
                    "Số EIR": o.eir_no or "—",
                    "Container": cntr_no,
                    "Dịch vụ": o.service_type.value,
                    "Số xe": o.truck_no,
                    "Phí nâng/hạ": format_vnd(o.handling_fee),
                    "Phí lưu bãi": format_vnd(o.storage_fee),
                    "Tổng (VAT 8%)": f"<b>{format_vnd(o.total_amount)}</b>",
                    "Trạng thái": status_val,
                    "QR Token": f"<code>{o.qr_token}</code>",
                }
            )
    return rows


def fetch_audit_logs() -> List[Dict[str, Any]]:
    with SessionLocal() as db:
        logs = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(15).all()
        return [
            {
                "Thời gian (GMT+7)": format_dt(l.created_at),
                "Người thực hiện": l.actor,
                "Hành động": l.action,
                "Đối tượng": l.target,
                "Chi tiết": l.detail,
            }
            for l in logs
        ]


def approve_customs_in_db(cntr_no: str, cleared: bool = True, actor: str = "admin_eport") -> tuple[bool, str]:
    with SessionLocal() as db:
        container = db.query(Container).filter(Container.cntr_no == cntr_no).first()
        if not container:
            return False, f"Không tìm thấy container {cntr_no}."
        container.customs_cleared = cleared
        state_text = "ĐÃ THÔNG QUAN" if cleared else "KHÓA THÔNG QUAN"
        db.add(
            AuditLog(
                actor=actor,
                action="CUSTOMS_UPDATE",
                target=cntr_no,
                detail=f"Cập nhật trạng thái Hải quan sang: {state_text}",
            )
        )
        db.commit()
        return True, f"Đã cập nhật container {cntr_no} sang trạng thái: {state_text}."

def build_eir_pdf_bytes(ci_data: Dict[str, Any]) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)

    if os.path.exists(r"C:\Windows\Fonts\arial.ttf"):
        pdf.add_font("VNFont", "", r"C:\Windows\Fonts\arial.ttf")
        pdf.add_font("VNFont", "B", r"C:\Windows\Fonts\arialbd.ttf")
    elif os.path.exists("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        pdf.add_font("VNFont", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        pdf.add_font("VNFont", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    else:
        pdf.add_font("VNFont", "", "/System/Library/Fonts/Supplemental/Arial.ttf")
        pdf.add_font("VNFont", "B", "/System/Library/Fonts/Supplemental/Arial Bold.ttf")

    # Khung viền ngoài A4
    pdf.set_draw_color(30, 41, 59)
    pdf.set_line_width(0.5)
    pdf.rect(8, 8, 194, 281)

    # 1. HEADER: LOGO VNTVT & THÔNG TIN CẢNG
    if os.path.exists("logo_transparent.png"):
        pdf.image("logo_transparent.png", x=12, y=10, w=23, h=21)
    else:
        pdf.set_fill_color(29, 78, 216)
        pdf.rect(12, 11, 22, 14, style="F")

    pdf.set_xy(37, 10)
    pdf.set_text_color(15, 23, 42)
    pdf.set_font("VNFont", "B", 11)
    pdf.cell(125, 5, "CÔNG TY CỔ PHẦN CẢNG QUỐC TẾ VNTVT", align="C", ln=True)
    pdf.set_x(37)
    pdf.set_font("VNFont", "", 7.5)
    pdf.cell(125, 4, "Khu Công Nghiệp Cảng Biển Quốc Tế, TP. Thủ Đức, TP. Hồ Chí Minh", align="C", ln=True)
    pdf.set_x(37)
    pdf.cell(125, 4, "Tel: (+84-28) 3899.6868   |   Email: eport@vntvt-port.vn   |   Mẫu: BM.01.03.EIR", align="C", ln=True)

    # Mã QR góc phải trên
    qr_b64 = generate_qr_base64(f"{ci_data.get('eir_no')}|{ci_data.get('cntr_no')}|{ci_data.get('truck_no')}")
    qr_stream = io.BytesIO(base64.b64decode(qr_b64))
    pdf.image(qr_stream, x=174, y=10, w=23, h=23)

    pdf.line(11, 34, 199, 34)

    # 2. TIÊU ĐỀ SONG NGỮ & SỐ PHIẾU
    pdf.set_xy(11, 36)
    pdf.set_font("VNFont", "B", 14)
    pdf.set_text_color(29, 78, 216)
    pdf.cell(135, 6, "PHIẾU GIAO NHẬN CONTAINER", align="C", ln=True)
    pdf.set_x(11)
    pdf.set_font("VNFont", "B", 10)
    pdf.cell(135, 5, "EQUIPMENT INTERCHANGE RECEIPT", align="C")

    pdf.set_xy(145, 36)
    pdf.set_font("VNFont", "B", 10)
    pdf.set_text_color(185, 28, 28)
    pdf.cell(53, 5, f"Số / Ref: {ci_data.get('eir_no', '—')}", ln=True)
    pdf.set_x(148)
    pdf.set_font("VNFont", "", 8)
    pdf.set_text_color(30, 41, 59)
    raw_ci = ci_data.get("checked_in_at")
    if isinstance(raw_ci, str) and raw_ci:
        try:
            dt_obj = datetime.fromisoformat(raw_ci.replace("Z", "+00:00"))
            if dt_obj.tzinfo is None:
                dt_obj = dt_obj.replace(tzinfo=timezone.utc)
            checked_str = dt_obj.astimezone(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")
        except ValueError:
            checked_str = raw_ci[:19].replace("T", " ")
    else:
        checked_str = datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")


    # 3. THÔNG TIN KHÁCH HÀNG & LỆNH GIAO HÀNG
    pdf.set_xy(11, 50)
    pdf.set_font("VNFont", "", 8)
    pdf.cell(56, 5, "Giao cho / Nhận của (Deliver/Receive):")
    pdf.set_font("VNFont", "B", 8.5)
    pdf.cell(132, 5, "CÔNG TY TNHH LOGISTICS PHƯƠNG NAM (PHUONG NAM LOGISTICS CO., LTD)", ln=True)


    pdf.set_x(11)
    pdf.set_font("VNFont", "", 8.5)
    pdf.cell(48, 5, "Mã lệnh ePort (eD/O Order No):")
    pdf.set_font("VNFont", "B", 9)
    pdf.cell(65, 5, f"{ci_data.get('order_code', '—')}")
    pdf.set_font("VNFont", "", 8.5)
    pdf.cell(35, 5, "Trạng thái Hải quan:")
    pdf.set_font("VNFont", "B", 8.5)
    pdf.set_text_color(22, 101, 52)
    pdf.cell(40, 5, "ĐÃ THÔNG QUAN (VNACCS)", ln=True)
    pdf.set_text_color(15, 23, 42)

    # 4. BẢNG THÔNG TIN CONTAINER & TÀU CHUYẾN
    y_tbl = 62
    pdf.set_line_width(0.3)

    def draw_grid_cell(x: float, y: float, w: float, h: float, vn_lbl: str, en_lbl: str, val: str, highlight: bool = False) -> None:
        pdf.rect(x, y, w, h)
        pdf.set_xy(x + 1.5, y + 1)
        pdf.set_font("VNFont", "", 7)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(w - 3, 3.2, f"{vn_lbl} / {en_lbl}", ln=True)
        pdf.set_xy(x + 1.5, y + 4.5)
        pdf.set_font("VNFont", "B", 9.5 if highlight else 8.5)
        pdf.set_text_color(29, 78, 216) if highlight else pdf.set_text_color(15, 23, 42)
        pdf.cell(w - 3, 4.5, val)

    draw_grid_cell(11, y_tbl, 45, 10, "Hãng tàu", "Shipping Line", "MAERSK / CMA-CGM")
    draw_grid_cell(56, y_tbl, 88, 10, "Tàu / Chuyến", "Vessel / Voyage", str(ci_data.get("vessel_info", "—")))
    draw_grid_cell(144, y_tbl, 55, 10, "Cảng xếp dỡ", "Port Code", "VNTVT PORT")

    y_tbl += 10
    draw_grid_cell(11, y_tbl, 45, 10, "Số B/L - Booking", "B/L No", f"BL-{str(ci_data.get('order_code', ''))[-6:]}")
    draw_grid_cell(56, y_tbl, 88, 10, "Số Container", "Container No", str(ci_data.get("cntr_no", "—")), highlight=True)
    draw_grid_cell(144, y_tbl, 55, 10, "Cỡ / Kiểu", "Size / Type", str(ci_data.get("size_type", "—")))

    y_tbl += 10
    draw_grid_cell(11, y_tbl, 45, 10, "Số chì hãng tàu", "Seal No", "SL-889412")
    draw_grid_cell(56, y_tbl, 44, 10, "Hàng / Rỗng", "Full / Empty", "EMPTY" if "RONG" in str(ci_data.get("service_type", "")) else "FULL")
    draw_grid_cell(100, y_tbl, 44, 10, "Vị trí bãi", "Yard Location", str(ci_data.get("yard_location", "—")), highlight=True)
    draw_grid_cell(144, y_tbl, 55, 10, "Trọng lượng", "Gross Weight", "2,250 KGS" if "RONG" in str(ci_data.get("service_type", "")) else "21,480 KGS")

    y_tbl += 10
    draw_grid_cell(11, y_tbl, 45, 10, "Tác nghiệp", "Operation", str(ci_data.get("service_type", "—")), highlight=True)
    draw_grid_cell(56, y_tbl, 88, 10, "Nơi trả vỏ / Hạ hàng", "Place of Return", "BÃI CONTAINER VNTVT")
    draw_grid_cell(144, y_tbl, 55, 10, "Tổng cước (VAT 8%)", "Total Paid", format_vnd(ci_data.get("total_amount", 0)))
    # 5. SƠ ĐỒ 6 MẶT CONTAINER (VẼ KỸ THUẬT CHUẨN MẪU EIR)
    y_diag = 105
    pdf.set_xy(11, y_diag)
    pdf.set_font("VNFont", "B", 7.5)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(188, 4, "Sử dụng mã dưới đây đánh dấu rõ ràng trên màn hình vẽ tình trạng container / Mark clearly in the condition of container using codes below:", ln=True)

    y_box = y_diag + 6
    pdf.set_draw_color(71, 85, 105)
    pdf.set_line_width(0.3)

    # Front Wall
    pdf.rect(18, y_box + 4, 20, 20)
    for step_x in range(21, 38, 3):
        pdf.line(step_x, y_box + 4, step_x, y_box + 24)
    pdf.set_xy(15, y_box + 25)
    pdf.set_font("VNFont", "", 6.5)
    pdf.cell(26, 3.5, "FRONT WALL", align="C")

    # L/H Side Panel
    pdf.rect(44, y_box + 4, 42, 20)
    for step_x in range(47, 86, 3):
        pdf.line(step_x, y_box + 4, step_x, y_box + 24)
    pdf.set_xy(44, y_box + 25)
    pdf.cell(42, 3.5, "L/H SIDE PANEL", align="C")

    # Door
    pdf.rect(90, y_box + 4, 20, 20)
    pdf.line(100, y_box + 4, 100, y_box + 24)
    pdf.line(93, y_box + 4, 93, y_box + 24)
    pdf.line(107, y_box + 4, 107, y_box + 24)
    pdf.set_xy(88, y_box + 25)
    pdf.cell(24, 3.5, "DOOR", align="C")

    # R/H Side Panel
    pdf.rect(114, y_box + 4, 42, 20)
    for step_x in range(117, 156, 3):
        pdf.line(step_x, y_box + 4, step_x, y_box + 24)
    pdf.set_xy(114, y_box + 25)
    pdf.cell(42, 3.5, "R/H SIDE PANEL", align="C")

    # Roof & Floor
    pdf.rect(162, y_box + 1, 32, 11)
    pdf.set_xy(162, y_box + 12.2)
    pdf.cell(32, 3, "ROOF (NÓC)", align="C")

    pdf.rect(162, y_box + 16, 32, 11)
    for step_x in range(165, 194, 3):
        pdf.line(step_x, y_box + 16, step_x, y_box + 27)
    pdf.set_xy(162, y_box + 27.2)
    pdf.cell(32, 3, "FLOOR (SÀN)", align="C")

    pdf.set_xy(11, y_box + 31)
    pdf.set_font("VNFont", "B", 7)
    pdf.cell(188, 4, "Ghi chú: Nếu không đánh dấu gì, container được coi giao nhận trong tình trạng tốt / If no mark, container is in good condition.")

    # 6. BẢNG MÃ LỖI & GHI CHÚ
    y_code = 148
    pdf.set_draw_color(30, 41, 59)
    pdf.rect(11, y_code, 95, 34)
    pdf.rect(106, y_code, 93, 34)

    pdf.set_xy(11, y_code + 1)
    pdf.set_font("VNFont", "B", 7.5)
    pdf.cell(95, 4, "Mã số hư hỏng / Condition Codes", align="C", ln=True)

    codes_left = ["BE: Cong (Bent)", "BO: Phình ra (Bulge Out)", "BR: Gãy (Broken)", "CU: Rách (Cut)", "CR: Vết rạn (Crack)", "DE: Vết lõm (Dent)"]
    codes_right = ["DI: Biến dạng (Distorted)", "DY: Bẩn (Dirty)", "H: Thủng (Hole)", "L: Lỏng (Loose)", "M: Thiếu (Missing)", "R: Rỉ sét (Rusty)"]
    pdf.set_font("VNFont", "", 7)
    for idx in range(6):
        pdf.set_xy(13, y_code + 6 + idx * 4.3)
        pdf.cell(45, 4, codes_left[idx])
        pdf.cell(46, 4, codes_right[idx])

    pdf.set_xy(108, y_code + 1)
    pdf.set_font("VNFont", "B", 7.5)
    pdf.cell(89, 4, "Ghi chú tình trạng thực tế / Remarks:", ln=True)
    pdf.set_xy(108, y_code + 7)
    pdf.set_font("VNFont", "", 8)
    pdf.multi_cell(
        89,
        4.5,
        f"- Container nguyên trạng (SOUND CONDITION), không móp méo.\n"
        f"- Nguyên chì hãng tàu & Hải quan.\n"
        f"- Chỉ định xe {ci_data.get('truck_no', '—')} vào làn Gate-In 01 đến Block {ci_data.get('yard_location', '—')}.",
    )

    # 7. BẢNG THEO DÕI XE VÀO / NÂNG HẠ / XE RA
    y_gate = 186
    draw_grid_cell(11, y_gate, 45, 11, "Số xe", "Vehicle Registered No", str(ci_data.get("truck_no", "—")), highlight=True)
    draw_grid_cell(56, y_gate, 50, 11, "Thời gian xe vào", "Time of Gate In", checked_str)
    draw_grid_cell(106, y_gate, 45, 11, "Nâng hạ trong bãi", "Lift On / Lift Off", "Đã xác nhận TOS")
    draw_grid_cell(151, y_gate, 48, 11, "Thời gian xe ra", "Time of Gate Out", "Theo quy định bãi")

    # 8. CHỮ KÝ 4 BÊN & CON DẤU MỘC ĐỎ VNTVT
    y_sig = 203
    sigs = [
        ("Bộ phận phát hành/Cổng", "Issuer / Smart Gate", "SMART GATE 01"),
        ("Nhân viên giao nhận", "Tally Officer", "ĐÃ KIỂM TRA BÃI"),
        ("Hải quan giám sát", "Customs Officer", "VNACCS CLEARED"),
        ("Đại diện chủ hàng / Tài xế", "Rep. of Consignee", f"Xe: {ci_data.get('truck_no', '—')}"),
    ]
    for i, (vn_s, en_s, note_s) in enumerate(sigs):
        x_s = 11 + i * 47.5
        pdf.set_xy(x_s, y_sig)
        pdf.set_font("VNFont", "B", 7.5)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(46, 4, vn_s, align="C", ln=True)
        pdf.set_x(x_s)
        pdf.set_font("VNFont", "", 7)
        pdf.cell(46, 3.5, en_s, align="C", ln=True)
        pdf.set_xy(x_s, y_sig + 24)
        pdf.set_font("VNFont", "B", 7.5)
        pdf.cell(46, 4, note_s, align="C")

    pdf.set_draw_color(220, 38, 38)
    pdf.set_line_width(0.6)
    pdf.rect(20, y_sig + 10, 44, 12)
    pdf.set_xy(20, y_sig + 11.5)
    pdf.set_font("VNFont", "B", 7.5)
    pdf.set_text_color(220, 38, 38)
    pdf.cell(44, 4, "VNTVT PORT TERMINAL", align="C", ln=True)
    pdf.set_x(20)
    pdf.set_font("VNFont", "", 6.5)
    pdf.cell(44, 3.5, "E-VERIFIED • GATE PASSED", align="C")

    # 9. GHI CHÚ 3 LIÊN
    pdf.set_xy(11, 278)
    pdf.set_font("VNFont", "", 7.5)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(62, 4, "Liên trắng: Lưu bộ phận phát hành (White: Issuer)", align="L")
    pdf.cell(64, 4, "Liên hồng: Lưu khách hàng (Pink: Customer)", align="C")
    pdf.cell(62, 4, "Liên vàng: Lưu Hải quan / Bảo vệ (Yellow: Gate)", align="R")

    return bytes(pdf.output())


def render_eir_receipt(ci_data: Dict[str, Any]) -> None:
    st.success(f"🎉 Đã phát hành chứng từ điện tử **{ci_data.get('eir_no')}** chuẩn mẫu cảng biển!")

    raw_ci = str(ci_data.get("checked_in_at", ""))
    try:
        dt_ci = datetime.fromisoformat(raw_ci.replace("Z", "+00:00"))
        vn_time_str = format_dt(dt_ci)
    except ValueError:
        vn_time_str = raw_ci or "—"

    eir_preview = (
        f'<div style="border:2px solid #0f172a;padding:22px;border-radius:10px;background:#ffffff;color:#0f172a;margin:10px 0;box-shadow:0 4px 10px rgba(0,0,0,0.06);">'
        f'<div style="display:flex;justify-content:space-between;border-bottom:2px solid #0f172a;padding-bottom:10px;">'
        f'<div><div style="font-weight:800;font-size:15px;">CẢNG CONTAINER QUỐC TẾ VNTVT</div><div style="font-size:12px;color:#475569;">Trung Tâm Điều Hành Cảng Điện Tử (ePort System)</div></div>'
        f'<div style="text-align:right;"><div style="font-weight:800;color:#b91c1c;font-size:15px;">PHIẾU GIAO NHẬN CONTAINER (EIR)</div><div style="font-size:13px;">Số phiếu: <b>{ci_data.get("eir_no")}</b></div></div>'
        f'</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:14px;font-size:13.5px;">'
        f'<div><b>Số Container:</b> <span style="font-size:15px;font-weight:700;color:#1d4ed8;">{ci_data.get("cntr_no")}</span> ({ci_data.get("size_type")})</div>'
        f'<div><b>Mã lệnh ePort:</b> {ci_data.get("order_code")}</div>'
        f'<div><b>Loại tác nghiệp:</b> {ci_data.get("service_type")}</div>'
        f'<div><b>Biển số xe đầu kéo:</b> {ci_data.get("truck_no")}</div>'
        f'<div><b>Vị trí bãi chỉ định:</b> <b style="color:#dc2626;">{ci_data.get("yard_location")}</b></div>'
        f'<div><b>Thời gian qua cổng:</b> {vn_time_str} (GMT+7)</div>'
        f'<div><b>Tàu / Chuyến:</b> {ci_data.get("vessel_info")}</div>'
        f'<div><b>Tổng cước đã thu:</b> <b>{format_vnd(ci_data.get("total_amount", 0))}</b></div>'
        f'</div>'
        f'<div style="margin-top:14px;padding:8px;background:#f8fafc;border:1px dashed #94a3b8;font-size:12px;border-radius:6px;">'
        f'<b>Kiểm tra kỹ thuật:</b> [✓] Vỏ nguyên vẹn &nbsp;|&nbsp; [✓] Kín nước &nbsp;|&nbsp; [✓] Nguyên chì hãng tàu / Hải quan'
        f'</div>'
        f'</div>'
    )
    st.markdown(eir_preview, unsafe_allow_html=True)

    with st.empty():
        pdf_bytes = build_eir_pdf_bytes(ci_data)

    st.download_button(
        label="📄 Tải xuống Phiếu EIR bản chuẩn (.PDF)",
        data=pdf_bytes,
        file_name=f"{ci_data.get('eir_no', 'EIR')}.pdf",
        mime="application/pdf",
        type="primary",
    )

def render_eir_lookup_section() -> None:
    st.divider()
    st.subheader("📄 Tra Cứu & Tải Phiếu EIR Điện Tử (e-EIR Portal)")
    st.caption("Tra cứu các phiếu giao nhận container đã xác nhận qua cổng Smart Gate để xem trước hoặc tải bản PDF có dấu mộc điện tử.")

    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        q_eir = st.text_input("🔎 Số phiếu EIR / Mã lệnh:", placeholder="VD: EIR-261125 hoặc ORD-...", key="eir_q_code").strip().upper()
    with col_s2:
        q_cntr = st.text_input("📦 Số Container:", placeholder="VD: MSKU1234566", key="eir_q_cntr").strip().upper()
    with col_s3:
        q_truck = st.text_input("🚛 Biển số xe đầu kéo:", placeholder="VD: 51C-889.66", key="eir_q_truck").strip().upper()

    with SessionLocal() as db:
        all_eirs = db.query(Order).filter(Order.eir_no.isnot(None)).order_by(Order.id.desc()).all()

        matched_orders = []
        for o in all_eirs:
            c_no = o.container.cntr_no if o.container else ""
            eir_str = o.eir_no or ""
            if q_eir and (q_eir not in eir_str and q_eir not in o.order_code):
                continue
            if q_cntr and (q_cntr not in c_no):
                continue
            if q_truck and (q_truck not in o.truck_no):
                continue
            matched_orders.append(o)

        if not matched_orders:
            st.info("Không tìm thấy phiếu EIR nào khớp với điều kiện tìm kiếm.")
            return

        # 1. Hiển thị bảng danh sách các phiếu EIR tìm thấy
        table_data = []
        eir_lookup_map = {}
        for o in matched_orders:
            c_obj = o.container
            c_no = c_obj.cntr_no if c_obj else "—"
            sz_type = c_obj.size_type.value if c_obj else "—"
            v_info = f"{c_obj.vessel.vessel_name} ({c_obj.vessel.voyage_no})" if (c_obj and c_obj.vessel) else "N/A"
            y_loc = c_obj.yard_location if (c_obj and c_obj.yard_location) else "Bãi chỉ định"

            table_data.append({
                "Số phiếu EIR": f"<b>{o.eir_no}</b>",
                "Mã lệnh ePort": o.order_code,
                "Số Container": f"<b>{c_no}</b>",
                "Cỡ/Loại": sz_type,
                "Tác nghiệp": o.service_type.value,
                "Biển số xe": o.truck_no,
                "Thời gian qua cổng": format_dt(o.checked_in_at),
            })

            label = f"{o.eir_no}  |  Cont: {c_no} ({sz_type})  |  Xe: {o.truck_no}  |  Lệnh: {o.order_code}"
            eir_lookup_map[label] = {
                "eir_no": o.eir_no,
                "order_code": o.order_code,
                "cntr_no": c_no,
                "size_type": sz_type,
                "service_type": o.service_type.value,
                "truck_no": o.truck_no,
                "yard_location": y_loc,
                "vessel_info": v_info,
                "total_amount": o.total_amount,
                "checked_in_at": o.checked_in_at.isoformat() if o.checked_in_at else "",
            }

        st.caption(f"Tìm thấy **{len(matched_orders)}** phiếu EIR điện tử hợp lệ:")
        render_html_table(table_data[:15])

        # 2. Chọn phiếu để Xem trước & Tải PDF
        st.markdown("#### 📥 Chọn phiếu để xem bản in & tải file PDF:")
        selected_label = st.selectbox("Danh sách phiếu EIR khớp điều kiện:", list(eir_lookup_map.keys()), key="eir_download_select")
        selected_eir_data = eir_lookup_map[selected_label]

        with st.expander("👁️ Xem trước nội dung Phiếu EIR điện tử", expanded=False):
            st.write(f"- **Số phiếu EIR:** `{selected_eir_data['eir_no']}` | **Mã lệnh:** `{selected_eir_data['order_code']}`")
            st.write(f"- **Container:** `{selected_eir_data['cntr_no']}` ({selected_eir_data['size_type']}) | **Vị trí bãi:** `{selected_eir_data['yard_location']}`")
            st.write(f"- **Biển số xe:** `{selected_eir_data['truck_no']}` | **Tàu/Chuyến:** {selected_eir_data['vessel_info']}")

        with st.empty():
            pdf_data = build_eir_pdf_bytes(selected_eir_data)

        st.download_button(
            label=f"📄 Tải xuống Phiếu {selected_eir_data['eir_no']} (.PDF)",
            data=pdf_data,
            file_name=f"{selected_eir_data['eir_no']}.pdf",
            mime="application/pdf",
            type="primary",
            key="btn_reprint_eir_pdf",
        )

@st.cache_resource
def start_embedded_backend() -> bool:
    def _run_uvicorn() -> None:
        import uvicorn
        from main import app as fastapi_app
        uvicorn.run(fastapi_app, host="127.0.0.1", port=8000, log_level="error")

    t = threading.Thread(target=_run_uvicorn, daemon=True)
    t.start()
    time.sleep(1.5)
    return True

def main() -> None:
    st.set_page_config(page_title="VNTVT Smart Port — Hệ thống Cảng Điện Tử", page_icon="⚓", layout="wide")
    start_embedded_backend()
    ensure_db_ready()
    inject_custom_css()

    for key in ["active_order", "payment_result", "last_lookup", "checkin_result"]:
        if key not in st.session_state:
            st.session_state[key] = None

    with st.sidebar:
        logo_b64 = get_transparent_logo_b64("logo.jpg")
        if logo_b64:
            st.markdown(
                f'<div style="text-align:center;margin:4px 0 12px 0;">'
                f'<div style="display:inline-block;background:#f8fafc;padding:10px 18px;border-radius:14px;box-shadow:0 4px 12px rgba(0,0,0,0.25);">'
                f'<img src="data:image/png;base64,{logo_b64}" style="width:120px;display:block;">'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        st.title("⚓ ePORT ENTERPRISE")
        st.caption("Mô phỏng Hệ thống Khai thác Cảng (Cát Lái / Gemadept Standard)")


        role_selected = st.selectbox(
            "🔐 Phân quyền đăng nhập (Role):",
            options=[
                "Customer — Chủ hàng",
                "Admin — Thương vụ & HQ",
                "Gate — Trạm Cổng SmartGate",
                "Guide — Hướng dẫn & Demo",
            ],
        )

        st.divider()
        api_base_url = st.text_input("Backend API URL", value=DEFAULT_API_BASE_URL)

        with st.expander("📋 Mã Container mẫu", expanded=True):
            with SessionLocal() as db:
                sample_cntrs = db.query(Container).limit(10).all()
                for c in sample_cntrs:
                    hq = "✅" if c.customs_cleared else "🔒"
                    st.markdown(f"`{c.cntr_no}` • {c.size_type.value} • {hq}")

        st.divider()
        st.caption("🎓 **Sản phẩm của Nhóm 9**\n\nQuản trị Vận tải Đa phương thức\n\nMã lớp HP: `[012041604622]`")


    # =========================================================================
    # VAI TRÒ 1: KHÁCH HÀNG / FORWARDER
    # =========================================================================
    if role_selected.startswith("Customer"):
        st.markdown('<div class="maritime-banner"><h1>⚓ CỔNG DỊCH VỤ KHÁCH HÀNG (ePORT CUSTOMER PORTAL)</h1><p>Khai báo lệnh làm hàng trực tuyến, tự động tính cước lưu bãi & thanh toán VietQR / eDO</p></div>', unsafe_allow_html=True)

        col_form, col_info = st.columns([1.1, 1.0], gap="large")

        with col_form:
            with st.form("create_order_form"):
                cntr_no_input = st.text_input("Số Container (ISO 6346)", placeholder="VD: MSKU1234566 hoặc TCLU7654328")
                service_type_input = st.selectbox(
                    "Loại tác nghiệp",
                    options=[s.value for s in ServiceType],
                    format_func=lambda val: {
                        "GIAO_NHAP": "GIAO_NHAP — Giao container hàng nhập (Import Full)",
                        "HA_XUAT": "HA_XUAT — Hạ container hàng xuất (Export Full)",
                        "CAP_RONG": "CAP_RONG — Cấp container rỗng (Empty Release)",
                        "TRA_RONG": "TRA_RONG — Hạ trả container rỗng (Empty Return)",
                    }.get(val, val),
                )
                truck_no_input = st.text_input("Biển số xe đầu kéo", placeholder="VD: 51C-889.66")

                b1, b2 = st.columns(2)
                with b1:
                    lookup_submitted = st.form_submit_button("🔍 Tra cứu & Tính cước")
                with b2:
                    create_submitted = st.form_submit_button("📝 Phát hành lệnh ePort", type="primary")

            if lookup_submitted and cntr_no_input.strip():
                ok, code, data = call_api(api_base_url, "GET", f"/api/containers/{cntr_no_input.strip().upper()}")
                if ok:
                    st.session_state["last_lookup"] = data
                else:
                    st.error(data.get("detail", "Lỗi tra cứu."))

            if create_submitted:
                cleaned_cntr = cntr_no_input.strip().upper()
                cleaned_truck = truck_no_input.strip().upper()
                if not cleaned_cntr or not cleaned_truck:
                    st.error("Vui lòng nhập đầy đủ Số Container và Biển số xe.")
                else:
                    ok, code, data = call_api(
                        api_base_url,
                        "POST",
                        "/api/orders",
                        json_payload={
                            "cntr_no": cleaned_cntr,
                            "service_type": service_type_input,
                            "truck_no": cleaned_truck,
                        },
                    )
                    if ok:
                        st.session_state["active_order"] = data
                        st.session_state["payment_result"] = None
                        st.success(f"Phát hành lệnh **{data['order_code']}** thành công!")
                    else:
                        st.error(f"Từ chối phát hành lệnh: {data.get('detail')}")

        with col_info:
            lookup_data = st.session_state.get("last_lookup")
            if lookup_data:
                with st.container(border=True):
                    st.subheader(f"🔎 Hồ sơ Container: `{lookup_data.get('cntr_no')}`")
                    st.write(f"- **Chuẩn ISO 6346:** {'✅ Hợp lệ' if lookup_data.get('is_iso6346_valid') else '❌ Sai Check-digit'}")
                    if lookup_data.get("found_in_yard"):
                        st.write(f"- **Kích cỡ / Trạng thái:** `{lookup_data.get('size_type')}` | `{lookup_data.get('status')}`")
                        st.write(f"- **Thanh lý Hải quan (VNACCS):** {'✅ Đã thông quan' if lookup_data.get('customs_cleared') else '❌ Chưa thông quan'}")
                        st.write(f"- **Hạn lệnh eD/O:** `{lookup_data.get('do_expiry_date') or 'Không áp dụng'}`")
                        st.write(f"- **Vị trí trên bãi:** `{lookup_data.get('yard_location')}`")
                    else:
                        st.warning("Container này chưa có dữ liệu trên bãi cảng.")

            active_order = st.session_state.get("active_order")
            if active_order:
                with st.container(border=True):
                    st.subheader("🧾 Chi tiết Biểu cước & Thanh toán")
                    render_order_stepper(active_order["payment_status"])
                    st.write(f"- **Mã lệnh:** `{active_order['order_code']}` | **Xe:** `{active_order['truck_no']}`")
                    st.write(f"- **Phí nâng/hạ (Handling):** {format_vnd(active_order['handling_fee'])}")
                    st.write(f"- **Phí lưu bãi quá hạn (DEM/Storage):** {format_vnd(active_order['storage_fee'])}")
                    st.markdown(f"#### Tổng thanh toán (gồm 8% VAT): **{format_vnd(active_order['total_amount'])}**")

                    if active_order["payment_status"] == "UNPAID":
                        if st.button("💳 Thanh toán trực tuyến (VietQR / Napas)", type="primary"):
                            ok_p, _, pay_data = call_api(api_base_url, "POST", f"/api/orders/{active_order['id']}/pay")
                            if ok_p:
                                st.session_state["payment_result"] = pay_data
                                st.session_state["active_order"]["payment_status"] = "PAID"
                                st.rerun()
                            else:
                                st.error(pay_data.get("detail"))

            payment_res = st.session_state.get("payment_result")
            if payment_res and payment_res.get("qr_base64"):
                with st.container(border=True):
                    st.success("✅ Đã thanh toán! Gửi mã QR này cho tài xế để qua cổng Smart Gate:")
                    qr_bytes = base64.b64decode(payment_res["qr_base64"])
                    st.image(qr_bytes, width=220)
                    st.code(payment_res["qr_token"], language="text")
        render_eir_lookup_section()

    # =========================================================================
    # VAI TRÒ 2: THƯƠNG VỤ & HẢI QUAN (DASHBOARD KPI + DUYỆT THÔNG QUAN + LOGS)
    # =========================================================================
    elif role_selected.startswith("Admin"):
        st.markdown('<div class="maritime-banner"><h1>📊 TRUNG TÂM ĐIỀU HÀNH THƯƠNG VỤ & HẢI QUAN (TOS DASHBOARD)</h1><p>Giám sát sản lượng bãi container (TEU), thanh lý tờ khai VNACCS & truy vết lịch sử hệ thống</p></div>', unsafe_allow_html=True)

        kpis = get_dashboard_kpis()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Tổng sản lượng bãi", f"{kpis['total_teu']} TEU", f"{kpis['total_containers']} Containers")
        k2.metric("Tỷ lệ thông quan VNACCS", f"{kpis['clearance_rate']:.1f}%")
        k3.metric("Doanh thu cước đã thu", format_vnd(kpis["total_revenue"]))
        k4.metric("Lượt xe đã qua cổng", f"{kpis['completed_gates']} lượt")
        render_svg_analytics()

        st.divider()
        st.subheader("1. Giám sát Bãi Container & Cập nhật Thông quan Hải quan")
        container_rows = fetch_containers_from_db()
        q_tbl = st.text_input("🔍 Lọc bảng dữ liệu chi tiết (nhập số Container hoặc Vị trí bãi):", key="tbl_filter").strip().upper()
        filtered_rows = [r for r in container_rows if not q_tbl or q_tbl in r["Số Container"] or q_tbl in r["Vị trí bãi"]]
        st.caption(f"Hiển thị {min(25, len(filtered_rows))} / {len(filtered_rows)} bản ghi:")
        render_html_table(filtered_rows[:25])

        with SessionLocal() as db:
            cntr_list = [c.cntr_no for c in db.query(Container).all()]

        c_sel, c_b1, c_b2 = st.columns([3, 1.2, 1.2])
        with c_sel:
            target_cntr = st.selectbox("Chọn Container cần xử lý nghiệp vụ Hải quan:", cntr_list)
        with c_b1:
            st.write("")
            st.write("")
            if st.button("✅ Duyệt thông quan", type="primary"):
                ok, msg = approve_customs_in_db(target_cntr, True)
                st.success(msg)
                st.rerun()
        with c_b2:
            st.write("")
            st.write("")
            if st.button("🔒 Khóa / Hủy thông quan"):
                ok, msg = approve_customs_in_db(target_cntr, False)
                st.warning(msg)
                st.rerun()

        st.divider()
        st.subheader("2. Quản lý Danh sách Lệnh ePort")
        render_html_table(fetch_orders_from_db())

        st.divider()
        st.subheader("3. Nhật ký Hệ thống (Audit Logs)")
        render_html_table(fetch_audit_logs())

    # =========================================================================
    # VAI TRÒ 3: ĐIỀU HÀNH CỔNG (SMART GATE + XUẤT PHIẾU EIR)
    # =========================================================================
    elif role_selected.startswith("Gate"):
        st.markdown('<div class="maritime-banner"><h1>🚧 TRẠM KIỂM SOÁT CỔNG THÔNG MINH (SMART GATE IN / OUT)</h1><p>Xác thực mã QR eDO tự động, kiểm tra thông quan real-time & phát hành phiếu EIR</p></div>', unsafe_allow_html=True)

        st.write("Quét mã QR Token từ điện thoại tài xế để đối chiếu thanh toán, kiểm tra Hải quan real-time và xuất phiếu EIR.")
        ci_ok = st.session_state.get("checkin_result")
        render_gate_led_board(bool(ci_ok), ci_ok.get("truck_no", "---") if ci_ok else "---", ci_ok.get("eir_no", "---") if ci_ok else "---")


        with SessionLocal() as db:
            recent_orders = db.query(Order).order_by(Order.id.desc()).limit(10).all()
            sample_tokens = [
                f"{o.order_code} | {o.truck_no} | {o.payment_status.value if hasattr(o.payment_status, 'value') else o.payment_status} -> {o.qr_token}"
                for o in recent_orders
            ]

        picked = st.selectbox("Chọn nhanh QR Token từ danh sách lệnh (để demo):", [""] + sample_tokens)
        default_tok = picked.partition(" -> ")[2] if " -> " in picked else ""

        with st.form("smart_gate_form"):
            token_in = st.text_input("Mã QR Token quét được:", value=default_tok)
            gate_submit = st.form_submit_button("🟢 Xác nhận mở Barrier & Xuất phiếu EIR", type="primary")

        if gate_submit and token_in.strip():
            ok_g, code_g, res_g = call_api(
                api_base_url,
                "POST",
                "/api/gate/checkin",
                json_payload={"qr_token": token_in.strip(), "gate_operator": "gate_01"},
            )
            if ok_g:
                st.session_state["checkin_result"] = res_g
                st.success(res_g.get("message"))
            else:
                st.session_state["checkin_result"] = None
                st.error(f"CẢNH BÁO TỪ CHỐI QUA CỔNG: {res_g.get('detail')}")

        if st.session_state.get("checkin_result"):
            render_eir_receipt(st.session_state["checkin_result"])

    # =========================================================================
    # VAI TRÒ 4: HƯỚNG DẪN CHI TIẾT CHO GIẢNG VIÊN & SINH VIÊN
    # =========================================================================
    elif role_selected.startswith("Guide"):
        st.markdown(
            '<div class="maritime-banner"><h1>📖 CẨM NANG VẬN HÀNH & TÀI LIỆU NGHIỆP VỤ VNTVT ePORT</h1>'
            '<p>Tài liệu hướng dẫn chi tiết dành cho Giảng viên đánh giá đồ án & Sinh viên / Người dùng thực hành</p></div>',
            unsafe_allow_html=True,
        )

        tab_gv, tab_sv, tab_test = st.tabs([
            "🎓 Dành cho Giảng viên (Kiến trúc & Nghiệp vụ)",
            "🧑‍💻 Dành cho Sinh viên (Hướng dẫn thao tác)",
            "🧪 5 Kịch bản Kiểm thử & Reset Dữ liệu",
        ])

        with tab_gv:
            st.subheader("1. Mục tiêu & Kiến trúc Mô phỏng Hệ thống Cảng Điện Tử")
            st.write(
                "Hệ thống **VNTVT Smart Port** mô phỏng quy trình khai thác container hiện đại theo mô hình **ePort kết hợp Smart Gate** "
                "(tương tự Cát Lái ePort / Gemadept), tách biệt rõ ràng giữa **Backend RESTful API (FastAPI + SQLAlchemy)** và **Frontend Dashboard (Streamlit)**."
            )

            col_g1, col_g2 = st.columns(2)
            with col_g1:
                with st.container(border=True):
                    st.markdown("#### ⚙️ Các Quy Tắc Nghiệp Vụ Cốt Lõi (Business Rules)")
                    st.markdown(
                        "- **Kiểm tra chuẩn quốc tế ISO 6346:** Tự động tính toán và đối chiếu chữ số kiểm tra (*Check-digit*) của mọi mã container trước khi truy vấn.\n"
                        "- **Đối khớp trạng thái khai thác:** Chặn tạo sai loại lệnh (VD: Cont đang `EMPTY` không thể làm lệnh `GIAO_NHAP`; Cont `EXPORT_FULL` bị chặn nếu quá giờ cắt máng *Closing Time*).\n"
                        "- **Tính phí lưu bãi tự động (DEM/Storage):** Miễn phí 3 ngày đầu (hàng nhập) hoặc 5 ngày (hàng xuất). Quá hạn tự động nhân đơn giá theo cỡ cont (`20GP`: 250k/ngày, `40HC`: 450k/ngày) + 8% VAT.\n"
                        "- **Chống tạo lệnh trùng lặp:** Một container đang có lệnh `UNPAID` hoặc `PAID` chưa qua cổng sẽ bị khóa, không thể phát hành lệnh thứ 2."
                    )
            with col_g2:
                with st.container(border=True):
                    st.markdown("#### 🛡️ Bảo Mật & Kiểm Soát Cổng Thông Minh (Smart Gate)")
                    st.markdown(
                        "- **Xác thực Hải quan thời gian thực (Real-time VNACCS Check):** Ngay tại giây phút xe quét QR ở cổng, hệ thống kiểm tra lại trạng thái thông quan và hạn lệnh `eD/O` (ngăn chặn trường hợp đã đóng tiền nhưng sau đó bị Hải quan khóa tờ khai).\n"
                        "- **Chống quay vòng mã QR (Anti-Fraud):** Ngay khi Barrier mở, lệnh chuyển sang `COMPLETED` và khóa vĩnh viễn mã QR. Quét lại lần 2 sẽ kích hoạt cảnh báo gian lận.\n"
                        "- **Chứng từ điện tử EIR chuẩn A4 (.PDF):** Tự động sinh số phiếu EIR, vẽ sơ đồ kỹ thuật 6 mặt container, gắn mã QR xác thực và dấu mộc điện tử.\n"
                        "- **Truy vết toàn diện (Audit Logs):** Lưu lại mọi thao tác tạo lệnh, thanh toán, duyệt thông quan và mở cổng theo múi giờ chuẩn Việt Nam (`GMT+7`)."
                    )

        with tab_sv:
            st.subheader("Hướng dẫn Thao tác Từng Bước cho Người Dùng Mới")
            st.info("💡 **Mẹo:** Bạn có thể chuyển đổi qua lại giữa 3 vai trò ở thanh menu màu tối bên trái (**Phân quyền đăng nhập**) để trải nghiệm trọn vẹn quy trình từ lúc khách khai báo đến lúc xe qua cổng.")

            with st.expander("📌 BƯỚC 1: Vai trò Chủ hàng / Forwarder (Khai báo & Thanh toán)", expanded=True):
                st.markdown(
                    "1. Ở thanh bên trái, chọn vai trò **`Chủ hàng / Forwarder (Customer)`**.\n"
                    "2. Copy một mã container ở mục *Mã Container mẫu* bên trái (ví dụ: `MSKU1234566` cho hàng nhập, hoặc `EMCU4455666` cho hàng xuất) dán vào ô **Số Container**.\n"
                    "3. Chọn **Loại tác nghiệp** tương ứng (`GIAO_NHAP`, `HA_XUAT`, `CAP_RONG`, hoặc `TRA_RONG`) và nhập **Biển số xe đầu kéo** (VD: `51C-889.66`).\n"
                    "4. Bấm **`🔍 Tra cứu & Tính cước`** để kiểm tra tình trạng Hải quan/eD/O, sau đó bấm **`📝 Phát hành lệnh ePort`**.\n"
                    "5. Kiểm tra bảng kê chi tiết phí nâng/hạ + phí lưu bãi, bấm **`💳 Thanh toán trực tuyến`** để nhận **Mã QR Token** giao cho tài xế."
                )

            with st.expander("📌 BƯỚC 2: Vai trò Thương vụ & Hải quan (Giám sát bãi & Duyệt thông quan)", expanded=True):
                st.markdown(
                    "1. Chuyển sang vai trò **`Thương vụ & Hải quan (Admin/Customs)`** ở menu bên trái.\n"
                    "2. Xem **4 chỉ số KPI tổng quan** (Sản lượng TEU, Tỷ lệ thông quan, Doanh thu, Lượt xe qua cổng) và **Biểu đồ phân tích tồn bãi**.\n"
                    "3. Sử dụng bộ lọc **Khu vực bãi (Block A - E)** để quan sát trực quan trạng thái từng container (Xanh lá: Sẵn sàng, Đỏ: Chờ Hải quan, Vàng: Hết hạn eD/O).\n"
                    "4. Tại mục **Cập nhật Thông quan Hải quan**, chọn một container bị khóa (VD: `HLXU8899117`) và bấm **`✅ Duyệt thông quan`** (hoặc **`🔒 Khóa thông quan`**) để thử nghiệm tác động ngay lập tức lên luồng làm lệnh."
                )

            with st.expander("📌 BƯỚC 3: Vai trò Điều hành Cổng (Quét QR & Xuất phiếu EIR PDF)", expanded=True):
                st.markdown(
                    "1. Chuyển sang vai trò **`Điều hành Cổng (Smart Gate)`** ở menu bên trái.\n"
                    "2. Ở ô **Chọn nhanh QR Token**, chọn một lệnh đang ở trạng thái **`PAID`** (hoặc dán mã QR vừa thanh toán ở Bước 1).\n"
                    "3. Bấm **`🟢 Xác nhận mở Barrier & Xuất phiếu EIR`**.\n"
                    "4. Quan sát **Bảng đèn LED cổng** chuyển sang màu xanh (`BARRIER OPEN`) và bấm **`📄 Tải xuống Phiếu EIR bản chuẩn (.PDF)`** để xem chứng từ A4 hoàn chỉnh."
                )
        with tab_test:
            st.subheader("Bộ 5 Kịch Bản Kiểm Thử Hệ Thống (Test Cases)")
            st.write("Giảng viên và Sinh viên có thể sử dụng các mã container dưới đây để kiểm thử nhanh toàn bộ tính năng của hệ thống:")

            with st.expander("📌 BƯỚC 4: Tra cứu & Tải lại Phiếu EIR Điện Tử (e-EIR Portal)", expanded=True):
                st.markdown(
                    "1. Quay lại vai trò **`Chủ hàng / Forwarder (Customer)`** và cuộn xuống mục **Tra Cứu & Tải Phiếu EIR Điện Tử** ở nửa dưới trang.\n"
                    "2. Nhập **Số phiếu EIR** (VD: `EIR-261125`), **Số Container**, hoặc **Biển số xe** để lọc nhanh các chứng từ đã qua cổng.\n"
                    "3. Chọn phiếu cần lấy trong danh sách thả xuống, bấm mở xem trước thông tin và nhấn **`📄 Tải xuống Phiếu EIR (.PDF)`** để lưu chứng từ có dấu mộc điện tử về máy."
                )

            test_cases = [
                {
                    "STT": "TC-01",
                    "Kịch bản kiểm thử": "Luồng chuẩn & Xuất phiếu EIR (.PDF)",
                    "Mã Container": "<code>MSKU1234566</code>",
                    "Thao tác thực hiện": "Vai trò Customer → Chọn <b>GIAO_NHAP</b> → Tạo lệnh & Thanh toán → Sang Smart Gate quét QR.",
                    "Kết quả mong đợi": "✅ Mở cổng thành công, xuất file PDF phiếu EIR song ngữ có mã QR & dấu mộc đỏ.",
                },
                {
                    "STT": "TC-02",
                    "Kịch bản kiểm thử": "Tự động tính phí lưu bãi quá hạn (DEM)",
                    "Mã Container": "<code>TCLU7654328</code>",
                    "Thao tác thực hiện": "Vai trò Customer → Chọn <b>GIAO_NHAP</b> cho cont này (đã lưu bãi 5 ngày, vượt 3 ngày miễn phí).",
                    "Kết quả mong đợi": "💰 Tự động cộng thêm <b>900.000 VNĐ</b> (2 ngày × 450.000đ) phí lưu bãi vào hóa đơn.",
                },
                {
                    "STT": "TC-03",
                    "Kịch bản kiểm thử": "Chặn Container chưa thông quan Hải quan",
                    "Mã Container": "<code>HLXU8899117</code>",
                    "Thao tác thực hiện": "Thử tạo lệnh <b>GIAO_NHAP</b> khi cont đang khóa HQ (🔒) → Sang vai trò Admin duyệt HQ → Quay lại tạo lệnh.",
                    "Kết quả mong đợi": "🔒 Bị từ chối khi chưa thông quan; cho phép tạo lệnh ngay sau khi Hải quan duyệt.",
                },
                {
                    "STT": "TC-04",
                    "Kịch bản kiểm thử": "Hạ container hàng xuất & Cấp/Trả rỗng",
                    "Mã Container": "<code>EMCU4455666</code><br><code>CAIU1122337</code>",
                    "Thao tác thực hiện": "Dùng <code>EMCU4455666</code> chọn <b>HA_XUAT</b>; dùng <code>CAIU1122337</code> chọn <b>CAP_RONG</b> hoặc <b>TRA_RONG</b>.",
                    "Kết quả mong đợi": "✅ Khớp đúng biểu cước từng loại dịch vụ và thời gian cắt máng tàu (Closing Time).",
                },
                {
                    "STT": "TC-05",
                    "Kịch bản kiểm thử": "Chống gian lận quay vòng mã QR tại Cổng",
                    "Mã Container": "Mã QR đã qua cổng",
                    "Thao tác thực hiện": "Tại Trạm Cổng (Smart Gate), bấm xác nhận qua cổng lần thứ 2 với cùng một mã QR đã dùng.",
                    "Kết quả mong đợi": "🚨 Hệ thống chặn đứng và hiển thị <b>Cảnh báo gian lận</b> do lệnh đã <code>COMPLETED</code>.",
                },
            ]
            render_html_table(test_cases)

            st.divider()
            st.subheader("🔄 Khôi phục Dữ liệu Mẫu (Reset Database)")
            st.warning("Lưu ý: Thao tác này sẽ đưa toàn bộ 120 container và danh sách lệnh về trạng thái khởi tạo ban đầu.")
            if st.button("🔄 Reset toàn bộ 120 Container & Dữ liệu gốc", type="primary"):
                from seed import seed_database
                seed_database()
                for k in ["active_order", "payment_result", "last_lookup", "checkin_result"]:
                    st.session_state[k] = None
                st.success("✅ Đã khôi phục toàn bộ 120 container và dữ liệu gốc thành công!")

    # =========================================================================
    # CHÂN TRANG BẢN QUYỀN ĐỒ ÁN (FOOTER)
    # =========================================================================
    st.markdown(
        """
        <div style="margin-top: 40px; padding: 16px 20px; border-top: 1px solid #cbd5e1;
                    background-color: #ffffff; border-radius: 10px; text-align: center;
                    color: #334155; font-size: 13.5px; box-shadow: 0 -2px 6px rgba(0,0,0,0.02);">
            ⚓ Hệ thống Mô phỏng Khai thác Cảng Điện Tử <b>VNTVT Smart Port</b><br>
            <span style="color: #0284c7; font-weight: 700; font-size: 14px;">
                Sản phẩm của Nhóm 9 - Quản trị Vận tải Đa phương thức - [012041604622]
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

if __name__ == "__main__":
    main()
