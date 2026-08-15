"""B: khi WebRTC DataChannel không bao giờ mở được (vd TURN không tới được -
lỗ hổng hạ tầng đã biết, xem comment đầu packages/transfer/webrtc_transport.py),
asyncio.wait_for(..., timeout=...) hết hạn với asyncio.TimeoutError - loại
exception này có str() RỖNG mặc định. Không bắt riêng thì người dùng thấy
dialog lỗi trắng không chữ thay vì hướng dẫn cụ thể. Test bằng fake
RTCPeerConnection/SignalingClient (không cần mạng thật) - datachannel cố ý
không bao giờ bắn event "open"/"datachannel" để ép đúng nhánh timeout đó."""

import asyncio

import pytest

from packages.transfer import webrtc_transport as wt


class _FakeDesc:
    def __init__(self, sdp: str):
        self.sdp = sdp


class _FakeChannel:
    def __init__(self):
        self._handlers = {}

    def on(self, event):
        def deco(fn):
            self._handlers[event] = fn
            return fn
        return deco

    @property
    def bufferedAmount(self):
        return 0

    def send(self, data):
        pass


class _FakePc:
    """Giả lập tối thiểu đúng bề mặt API send_file()/receive_file() dùng tới.
    iceGatheringState = "complete" ngay từ đầu để _wait_ice_gathering_complete()
    không phải chờ thật. Datachannel "open"/"datachannel" cố ý KHÔNG bao giờ
    được kích hoạt - mô phỏng ICE/TURN không bao giờ thiết lập được kết nối
    thật, dù đã trao đổi SDP xong."""

    def __init__(self):
        self.iceGatheringState = "complete"
        self.localDescription = _FakeDesc("fake-local-sdp")
        self._handlers = {}
        self.channel = _FakeChannel()

    def on(self, event):
        def deco(fn):
            self._handlers[event] = fn
            return fn
        return deco

    def createDataChannel(self, name, ordered=True):
        return self.channel

    async def createOffer(self):
        return _FakeDesc("fake-offer-sdp")

    async def createAnswer(self):
        return _FakeDesc("fake-answer-sdp")

    async def setLocalDescription(self, desc):
        self.localDescription = desc

    async def setRemoteDescription(self, desc):
        pass

    async def close(self):
        pass


class _FakeSignalingSend:
    """Phía gửi: trả lời sdp_answer ngay lần receive() đầu tiên."""

    def __init__(self):
        self.closed = False

    async def connect(self):
        pass

    async def send_sdp_offer(self, sdp):
        pass

    async def receive(self):
        return {"type": "sdp_answer", "sdp": "fake-answer-sdp"}

    async def close(self):
        self.closed = True


class _FakeSignalingReceive:
    """Phía nhận: trả lời sdp_offer ngay lần receive() đầu tiên."""

    def __init__(self):
        self.closed = False

    async def connect(self):
        pass

    async def receive(self):
        return {"type": "sdp_offer", "sdp": "fake-offer-sdp"}

    async def send_sdp_answer(self, sdp):
        pass

    async def close(self):
        self.closed = True


def test_send_file_channel_never_opens_raises_transfer_error_with_message(tmp_path, monkeypatch):
    fake_pc = _FakePc()
    monkeypatch.setattr(wt, "_make_pc", lambda: fake_pc)

    src = tmp_path / "doc.pdf"
    src.write_bytes(b"%PDF-1.4 fake content")

    async def run():
        with pytest.raises(wt.TransferError) as excinfo:
            await wt.send_file(_FakeSignalingSend(), str(src), channel_open_timeout=0.05)
        return excinfo.value

    err = asyncio.run(run())
    assert str(err), "TransferError must carry a non-empty, actionable message"
    assert "kết nối" in str(err).lower()


def test_receive_file_channel_never_opens_raises_transfer_error_with_message(monkeypatch):
    fake_pc = _FakePc()
    monkeypatch.setattr(wt, "_make_pc", lambda: fake_pc)

    async def run():
        with pytest.raises(wt.TransferError) as excinfo:
            await wt.receive_file(_FakeSignalingReceive(), channel_open_timeout=0.05)
        return excinfo.value

    err = asyncio.run(run())
    assert str(err), "TransferError must carry a non-empty, actionable message"
    assert "kết nối" in str(err).lower()
