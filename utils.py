import base64
import io
import re
from typing import Dict

import qrcode
from qrcode.constants import ERROR_CORRECT_M


ISO6346_LETTER_VALUES: Dict[str, int] = {
    "A": 10, "B": 12, "C": 13, "D": 14, "E": 15, "F": 16, "G": 17, "H": 18, "I": 19,
    "J": 20, "K": 21, "L": 23, "M": 24, "N": 25, "O": 26, "P": 27, "Q": 28, "R": 29,
    "S": 30, "T": 31, "U": 32, "V": 34, "W": 35, "X": 36, "Y": 37, "Z": 38,
}

ISO6346_PATTERN = re.compile(r"^[A-Z]{4}[0-9]{7}$")


def calculate_iso6346_check_digit(first_ten_chars: str) -> int:
    """
    Tính check-digit theo chuẩn ISO 6346 từ 10 ký tự đầu tiên (3 chữ cái chủ sở hữu +
    1 chữ cái loại thiết bị + 6 chữ số serial).
    Trọng số vị trí i (0..9) là 2^i, chia tổng cho 11 lấy dư, nếu bằng 10 thì trả về 0.
    """
    if len(first_ten_chars) != 10:
        raise ValueError("Chuỗi đầu vào phải có đúng 10 ký tự.")

    total = 0
    for index, char in enumerate(first_ten_chars):
        if char.isalpha():
            val = ISO6346_LETTER_VALUES[char]
        elif char.isdigit():
            val = int(char)
        else:
            raise ValueError(f"Ký tự không hợp lệ trong mã ISO 6346: {char}")

        weight = 2 ** index
        total += val * weight

    remainder = total % 11
    return 0 if remainder == 10 else remainder


def validate_iso6346(cntr_no: str) -> bool:
    """
    Kiểm tra tính hợp lệ của số container theo chuẩn quốc tế ISO 6346:
    - Đúng 11 ký tự: 4 chữ cái viết hoa + 7 chữ số (6 số serial + 1 check-digit).
    - Chữ cái thứ 4 phải là U, J, hoặc Z (thiết bị chở hàng / container).
    - Chữ số thứ 11 khớp với check-digit tính toán.
    """
    if not isinstance(cntr_no, str):
        return False

    normalized = cntr_no.strip().upper()
    if not ISO6346_PATTERN.match(normalized):
        return False

    equipment_category_identifier = normalized[3]
    if equipment_category_identifier not in {"U", "J", "Z"}:
        return False

    expected_check_digit = calculate_iso6346_check_digit(normalized[:10])
    actual_check_digit = int(normalized[10])
    return expected_check_digit == actual_check_digit


def generate_qr_base64(payload: str, box_size: int = 8, border: int = 2) -> str:
    """
    Sinh mã QR từ chuỗi payload (ví dụ qr_token hoặc dữ liệu lệnh cổng) và trả về
    chuỗi Base64 (PNG) để nhúng trực tiếp vào thẻ <img src="data:image/png;base64,...">
    hoặc trả qua API FastAPI.
    """
    if not payload or not isinstance(payload, str):
        raise ValueError("Payload để tạo mã QR không được rỗng.")

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    encoded_bytes = base64.b64encode(buffer.getvalue())
    return encoded_bytes.decode("utf-8")