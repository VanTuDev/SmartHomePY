"""
telegram_service.py - Gui canh bao qua Telegram Bot
"""
import base64
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "")
_BASE  = f"https://api.telegram.org/bot{_TOKEN}"


def _ok() -> bool:
    return bool(_TOKEN and _CHAT)


def send_message(text: str) -> bool:
    if not _ok():
        print("Telegram chua duoc cau hinh.")
        return False
    try:
        r = requests.post(
            f"{_BASE}/sendMessage",
            json={"chat_id": _CHAT, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram send_message loi: {e}")
        return False


def send_photo(image_b64: str, caption: str) -> bool:
    if not _ok():
        print("Telegram chua duoc cau hinh.")
        return False
    try:
        image_bytes = base64.b64decode(image_b64)
        r = requests.post(
            f"{_BASE}/sendPhoto",
            data={"chat_id": _CHAT, "caption": caption},
            files={"photo": ("snapshot.jpg", image_bytes, "image/jpeg")},
            timeout=15,
        )
        if r.status_code == 200:
            print("Telegram: Gui anh thanh cong.")
            return True
        else:
            print(f"Telegram loi {r.status_code}: {r.text}")
            return False
    except Exception as e:
        print(f"Telegram send_photo loi: {e}")
        return False


def alert_stranger(image_b64: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    caption = (
        f"CANH BAO: Co nguoi la co gang mo cua!\n"
        f"Thoi gian: {ts}\n"
        f"He thong da tu choi truy cap."
    )
    ok = send_photo(image_b64, caption)
    if not ok:
        print("Telegram: Gui canh bao that bai.")


def alert_fall(image_b64: str, timestamp: str) -> None:
    """Canh bao khan cap khi phat hien te nga."""
    caption = (
        f"CANH BAO KHAN CAP: Phat hien nguoi nga!\n"
        f"Thoi gian: {timestamp}\n"
        f"Vui long kiem tra ngay!"
    )
    ok = send_photo(image_b64, caption)
    if not ok:
        print("Telegram: Gui canh bao te nga that bai.")


def alert_doorbell_known(name: str, image_b64: str) -> None:
    """Nguoi quen bam chuong."""
    ts = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    caption = (
        f"CHUONG CUA: {name} dang o truoc cua!\n"
        f"Thoi gian: {ts}"
    )
    ok = send_photo(image_b64, caption)
    if not ok:
        print("Telegram: Gui thong bao chuong that bai.")


def alert_doorbell_stranger(image_b64: str) -> None:
    """Nguoi la bam chuong."""
    ts = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    caption = (
        f"CANH BAO CHUONG CUA: Co nguoi la bam chuong!\n"
        f"Thoi gian: {ts}\n"
        f"Hay kiem tra camera ngay."
    )
    ok = send_photo(image_b64, caption)
    if not ok:
        print("Telegram: Gui canh bao chuong that bai.")
