"""Rate-limit + token TTL thuần cho main_api.

Tách khỏi main_api.py để test được: main_api phụ thuộc `.services.*` (chỉ có
trên VPS) nên không import/chạy được ở máy dev; các hàm ở đây chỉ dùng stdlib.
"""
from __future__ import annotations

import time


def rate_check(
    buckets: dict,
    key,
    max_hits: int,
    window_s: float,
    now: float | None = None,
) -> bool:
    """Fixed-window limiter trong bộ nhớ.

    Trả về True nếu request được phép (và ghi nhận 1 hit), False nếu đã vượt
    ngưỡng `max_hits` trong `window_s` giây gần nhất cho `key`.
    """
    if now is None:
        now = time.time()
    hits = [t for t in buckets.get(key, []) if now - t < window_s]
    if len(hits) >= max_hits:
        buckets[key] = hits
        return False
    hits.append(now)
    buckets[key] = hits
    return True


def token_active(expires_at: float | None, now: float | None = None) -> bool:
    """True nếu token còn hạn (chưa tới thời điểm `expires_at`)."""
    if expires_at is None:
        return False
    if now is None:
        now = time.time()
    return now <= float(expires_at)
