"""Test logic thuần rate-limit + token TTL của main_api (tách ở vps_auth_limits)."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "vps_auth_limits", Path(__file__).resolve().parents[1] / "vps_auth_limits.py"
)
val = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(val)


def test_rate_check_allows_up_to_limit_then_blocks():
    buckets = {}
    key = ("login", "1.2.3.4")
    # 5 lần đầu trong cùng cửa sổ đều được phép
    for i in range(5):
        assert val.rate_check(buckets, key, 5, 300, now=1000 + i) is True
    # lần thứ 6 bị chặn
    assert val.rate_check(buckets, key, 5, 300, now=1005) is False


def test_rate_check_resets_after_window():
    buckets = {}
    key = ("login", "1.2.3.4")
    for i in range(5):
        assert val.rate_check(buckets, key, 5, 300, now=1000 + i) is True
    assert val.rate_check(buckets, key, 5, 300, now=1005) is False
    # sau khi cửa sổ trôi qua, được phép lại
    assert val.rate_check(buckets, key, 5, 300, now=1000 + 301) is True


def test_rate_check_isolated_per_key():
    buckets = {}
    for i in range(5):
        val.rate_check(buckets, ("login", "1.1.1.1"), 5, 300, now=1000 + i)
    assert val.rate_check(buckets, ("login", "1.1.1.1"), 5, 300, now=1005) is False
    # IP khác không bị ảnh hưởng
    assert val.rate_check(buckets, ("login", "2.2.2.2"), 5, 300, now=1005) is True


def test_token_active():
    assert val.token_active(None) is False
    assert val.token_active(2000, now=1000) is True
    assert val.token_active(1000, now=2000) is False
    assert val.token_active(1000, now=1000) is True  # đúng biên còn hạn
