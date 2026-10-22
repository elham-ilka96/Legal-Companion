
import requests
from django.conf import settings


# =========================================================
# تنظیمات اتصال به Paperless-ngx
# =========================================================

PAPERLESS_URL = getattr(
    settings,
    "PAPERLESS_URL",
    "http://127.0.0.1:8002",
).rstrip("/")

# پشتیبانی از هر دو نام برای سازگاری با تنظیمات قبلی
PAPERLESS_TOKEN = (
    getattr(settings, "PAPERLESS_API_TOKEN", "")
    or getattr(settings, "PAPERLESS_TOKEN", "")
)


def get_headers():
    """ساخت هدر احراز هویت برای API پیپرلس."""
    return {
        "Authorization": f"Token {PAPERLESS_TOKEN}",
    }


def upload_document(file_path, title=None, tags=None):
    """ارسال فایل به Paperless و دریافت شناسه پردازش."""

    if not PAPERLESS_TOKEN:
        return {
            "success": False,
            "error": "توکن Paperless در تنظیمات Django تعریف نشده است.",
        }

    url = f"{PAPERLESS_URL}/api/documents/post_document/"

    data = {}

    if title:
        data["title"] = title

    if tags:
        data["tags"] = tags

    try:
        with open(file_path, "rb") as file:
            response = requests.post(
                url,
                headers=get_headers(),
                files={"document": file},
                data=data,
                timeout=60,
            )

        if not response.ok:
            return {
                "success": False,
                "error": (
                    f"Paperless HTTP {response.status_code}: "
                    f"{response.text[:1000]}"
                ),
            }

        try:
            result = response.json()
        except ValueError:
            return {
                "success": False,
                "error": "پاسخ Paperless قابل خواندن نیست.",
            }

        # بسته به نسخه، پاسخ می‌تواند UUID یا یک شیء JSON باشد.
        if isinstance(result, str):
            task_id = result
        elif isinstance(result, dict):
            task_id = (
                result.get("task_id")
                or result.get("task")
                or result.get("id")
            )
        else:
            task_id = None

        if not task_id:
            return {
                "success": False,
                "error": f"شناسه پردازش در پاسخ پیدا نشد: {result}",
            }

        return {
            "success": True,
            "task_id": str(task_id),
        }

    except requests.RequestException as exc:
        return {
            "success": False,
            "error": f"خطا در ارتباط با Paperless: {exc}",
        }

    except OSError as exc:
        return {
            "success": False,
            "error": f"خطا در خواندن فایل: {exc}",
        }


def get_task_status(task_uuid):
    """بررسی وضعیت پردازش سند."""

    if not PAPERLESS_TOKEN:
        return None

    url = f"{PAPERLESS_URL}/api/tasks/"

    try:
        response = requests.get(
            url,
            headers=get_headers(),
            params={"task_id": task_uuid},
            timeout=15,
        )

        if response.ok:
            return response.json()

    except (requests.RequestException, ValueError) as exc:
        # به‌جای raise کردن، خطا رو لاگ می‌کنیم و None برمی‌گردونیم
        print(f"[Paperless] get_task_status error: {exc}")

    return None

def search_documents(query):
    """جست‌وجو در اسناد Paperless."""

    if not PAPERLESS_TOKEN:
        return None

    url = f"{PAPERLESS_URL}/api/documents/"

    try:
        response = requests.get(
            url,
            headers=get_headers(),
            params={"search": query},
            timeout=15,
        )

        if response.ok:
            return response.json()

    except (requests.RequestException, ValueError):
        pass

    return None


def get_document_content(document_id):
    """دریافت متن استخراج‌شده از سند."""

    if not PAPERLESS_TOKEN:
        return None

    url = f"{PAPERLESS_URL}/api/documents/{document_id}/"

    try:
        response = requests.get(
            url,
            headers=get_headers(),
            timeout=15,
        )

        if response.ok:
            return response.json().get("content", "")

    except (requests.RequestException, ValueError):
        pass

    return None
