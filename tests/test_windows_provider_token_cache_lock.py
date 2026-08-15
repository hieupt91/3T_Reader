"""WindowsPkcs11Provider.list_tokens() race (bug hunt finding, Medium):
get_signing_provider() is a module-level singleton shared between the UI
thread and the background _TokenPresenceWorker QThread (polls every 15s).
Both read/write _tokens_cache*/`_tokens_cache_until` with no lock - if both
see the cache expired at the same moment, both run a full duplicate PKCS11
probe (defeats the B1/B2 caching perf fix). Verify the lock actually
serializes concurrent calls instead of just asserting it exists in source.
"""

import threading
import time

from packages.signing.windows_provider import WindowsPkcs11Provider


def test_concurrent_list_tokens_calls_do_not_run_the_scan_twice(monkeypatch):
    provider = WindowsPkcs11Provider()
    scan_count = 0
    scan_started = threading.Event()
    release_scan = threading.Event()
    b_about_to_call = threading.Event()

    def fake_candidate_paths():
        nonlocal scan_count
        scan_count += 1
        scan_started.set()
        # Hold the "scan in progress" window open until thread_b has had a
        # chance to call list_tokens() too - if the lock did NOT serialize
        # them, thread_b would see the cache as still expired and run its
        # own second scan right here.
        b_about_to_call.wait(timeout=5.0)
        time.sleep(0.2)
        release_scan.wait(timeout=5.0)
        return []

    monkeypatch.setattr(
        "packages.signing.windows_provider._candidate_paths", fake_candidate_paths
    )

    def call_a():
        provider.list_tokens()

    def call_b():
        b_about_to_call.set()
        provider.list_tokens()  # must block on the lock until thread_a finishes

    thread_a = threading.Thread(target=call_a)
    thread_a.start()
    assert scan_started.wait(timeout=5.0), "thread_a never started its scan"

    thread_b = threading.Thread(target=call_b)
    thread_b.start()
    time.sleep(0.3)  # give thread_b a real chance to race in if unlocked
    release_scan.set()

    thread_a.join(timeout=5.0)
    thread_b.join(timeout=5.0)

    assert scan_count == 1, f"expected exactly 1 scan, got {scan_count}"


def test_lock_exists_and_is_a_plain_non_reentrant_lock():
    """list_tokens() does no Qt event pumping (pure subprocess/registry/
    filesystem work), so unlike app/actions/_pdf_save.py's pdf_write_slot
    (which must tolerate same-thread reentrancy), a plain threading.Lock is
    safe and appropriate here - confirms the type wasn't over-engineered
    into something unnecessary."""
    provider = WindowsPkcs11Provider()
    assert type(provider._tokens_lock).__name__ == "lock"
