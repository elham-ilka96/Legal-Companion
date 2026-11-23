# accounts/services/anonymizer.py
import re
from accounts.models import CaseParticipant

ROLE_MAP = {
    "plaintiff": "خواهان",
    "defendant": "خوانده",
    "witness": "شاهد",
    "lawyer": "وکیل",
    "judge": "قاضی",
    "expert": "کارشناس",
    "other": "طرف پرونده",
}


def _normalize(s: str) -> str:
    if not s:
        return ""
    return (
        s.replace("ي", "ی")
        .replace("ك", "ک")
        .replace("\u200c", " ")
        .replace("\u200f", "")
        .replace("\u200e", "")
        .strip()
    )


def _person_name_variants(person) -> set:
    variants = set()

    # اگر مدل Person فیلد full_name داره
    full = getattr(person, "full_name", None)
    if full:
        variants.add(_normalize(full))

    first = getattr(person, "first_name", "") or ""
    last = getattr(person, "last_name", "") or ""
    combined = f"{first} {last}".strip()
    if combined:
        variants.add(_normalize(combined))

    # اگر فیلد name داره
    name = getattr(person, "name", None)
    if name:
        variants.add(_normalize(name))

    # اسم کامل بدون فاصله
    if first and last:
        variants.add(_normalize(f"{first}{last}"))

    return {v for v in variants if v and len(v) > 2}


def build_name_role_pairs(case) -> list:
    """
    لیست (نام, نقش) برای همه شرکت‌کنندگان پرونده.
    بلندترین اسم اول، تا زیرمجموعه‌ها مشکل نسازن.
    """
    pairs = []
    participants = (
        CaseParticipant.objects
        .filter(case=case)
        .select_related("person")
    )
    for p in participants:
        role = ROLE_MAP.get(getattr(p, "role", None), "طرف پرونده")
        for variant in _person_name_variants(p.person):
            pairs.append((variant, role))

    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    return pairs


def anonymize_text(text: str, case) -> str:
    """
    اسم همه افراد مرتبط با پرونده رو با نقششون جایگزین می‌کنه.
    """
    if not text:
        return text

    normalized_text = _normalize(text)
    pairs = build_name_role_pairs(case)

    for name, role in pairs:
        # نسخه نرمال‌شده رو با نقش جایگزین کن
        normalized_text = normalized_text.replace(name, role)

        # نسخه اصلی (بدون نرمال‌سازی) رو هم اگه توی متن اصلی هست بگیر
        for original_variant in {name}:
            pass

    # در آخر نسخه نرمال‌شده رو برگردون (چون متن فارسی معمولاً یکسانه)
    return normalized_text