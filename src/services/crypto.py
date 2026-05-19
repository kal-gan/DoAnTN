"""
src/services/crypto.py
Mã hoá / giải mã các bí mật (SMTP password, …) lưu trong CSDL.

Sử dụng Fernet (AES-128 CBC + HMAC SHA-256) của thư viện ``cryptography``.
Khoá được sinh ngẫu nhiên trong lần đầu chạy và lưu trong file ``.app_key``
ở thư mục làm việc. File khoá KHÔNG được commit vào git
(đã có entry trong ``.gitignore``).

Định dạng ciphertext trong DB có tiền tố ``enc:`` để phân biệt với chuỗi
plaintext cũ (giúp migrate êm: giá trị không có tiền tố sẽ được coi là
plaintext và mã hoá lại trong lần lưu tiếp theo).
"""
from __future__ import annotations

import os
from typing import Optional

try:
    from cryptography.fernet import Fernet, InvalidToken
    _CRYPTO_AVAILABLE = True
except Exception:  # pragma: no cover
    _CRYPTO_AVAILABLE = False
    Fernet = None  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[assignment, misc]


_PREFIX = "enc:"
_KEY_FILE = ".app_key"


def _key_path() -> str:
    return os.path.abspath(_KEY_FILE)


def _load_or_create_key() -> Optional[bytes]:
    """Đọc khoá Fernet từ file; nếu chưa có, sinh mới và lưu."""
    if not _CRYPTO_AVAILABLE:
        return None
    path = _key_path()
    try:
        if os.path.isfile(path):
            with open(path, "rb") as f:
                key = f.read().strip()
            if key:
                return key
        key = Fernet.generate_key()  # type: ignore[union-attr]
        with open(path, "wb") as f:
            f.write(key)
        # Cố gắng hạn chế quyền đọc trên hệ điều hành hỗ trợ
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass
        return key
    except Exception:
        return None


def _fernet() -> Optional["Fernet"]:
    if not _CRYPTO_AVAILABLE:
        return None
    key = _load_or_create_key()
    if not key:
        return None
    try:
        return Fernet(key)  # type: ignore[misc]
    except Exception:
        return None


def encrypt_secret(plaintext: str) -> str:
    """Mã hoá chuỗi; trả về ``"enc:<base64>"``.

    Nếu thư viện ``cryptography`` không có hoặc lỗi, trả về plaintext nguyên
    vẹn (fail-open) để không làm gãy luồng người dùng.
    """
    if not plaintext:
        return ""
    f = _fernet()
    if f is None:
        return plaintext
    try:
        token = f.encrypt(plaintext.encode("utf-8")).decode("ascii")
        return _PREFIX + token
    except Exception:
        return plaintext


def decrypt_secret(value: str) -> str:
    """Giải mã chuỗi; chấp nhận cả ciphertext (``enc:…``) và plaintext cũ."""
    if not value:
        return ""
    if not value.startswith(_PREFIX):
        # Plaintext cũ — trả về như cũ để giữ tương thích ngược
        return value
    f = _fernet()
    if f is None:
        return ""
    try:
        return f.decrypt(value[len(_PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken:
        return ""
    except Exception:
        return ""


def is_encrypted(value: str) -> bool:
    return bool(value) and value.startswith(_PREFIX)
