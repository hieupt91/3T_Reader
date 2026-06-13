"""Unit tests for packages.platform.single_instance — mutex/lock behavior."""

import time

from packages.platform.single_instance import (
    acquire_single_instance,
    send_paths_to_running_instance,
    start_single_instance_server,
)


class TestAcquireSingleInstance:
    def test_returns_bool(self):
        """acquire_single_instance always returns a bool."""
        result = acquire_single_instance()
        assert isinstance(result, bool)


def test_second_instance_can_forward_pdf_path(tmp_path):
    pdf_path = tmp_path / "second.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")
    received = []

    start_single_instance_server(lambda paths: received.extend(paths))

    assert send_paths_to_running_instance([str(pdf_path)], timeout=1.0) is True

    deadline = time.time() + 2
    while time.time() < deadline and not received:
        time.sleep(0.05)

    assert received == [str(pdf_path)]
