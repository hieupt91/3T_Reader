"""Deploy script dùng SSH LAN trực tiếp (192.168.1.254:2222), KHÔNG qua
cloudflared tunnel - tunnel qua ssh.3tcomputer.com từng bị treo/chết giữa
chừng khi upload file lớn (xem docs/HANDOFF_TRANSFER_WIN_VPS_2026-08-14.md).
Máy build và VPS là CÙNG mạng LAN nội bộ nên SSH thẳng nhanh và ổn định hơn
nhiều (~20s cho file ~500MB so với treo vô thời hạn qua tunnel).
"""
import hashlib
import json
import os
import sys

import paramiko

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from app.version import APP_VERSION
from vps_secret import vps_password

VERSION = APP_VERSION
BASE_URL = "https://reader.3tcomputer.com/downloads"
PUBLIC_INSTALLER_NAME = f"3TReader-{VERSION}-win-r7.exe"
PUBLIC_PORTABLE_NAME = f"3TReader-{VERSION}-win-portable-r7.zip"
RELEASE_NOTES = (
    "Phiên bản 1.0.31 (bản build đầy đủ): dùng Microsoft Office/WPS Office "
    "đã cài sẵn (nếu có) để chuyển Word/Excel sang PDF - nhanh và ổn định "
    "hơn, tự chuyển sang LibreOffice nếu máy không có Office/WPS; sửa lỗi "
    "app bị treo/không phản hồi ngẫu nhiên lúc mở file Word/Excel lần đầu "
    "(chuyển bước chuyển đổi sang chạy nền thay vì chặn giao diện); gỡ hoàn "
    "toàn thư viện PyMuPDF (giấy phép AGPL) khỏi ứng dụng, thay bằng "
    "pypdfium2 + pikepdf (giấy phép thoáng hơn) cho toàn bộ thao tác đọc/"
    "chỉnh sửa PDF, đã kiểm thử đối chiếu kỹ trước khi thay; thêm tính năng "
    "\"Xuất log để báo lỗi\" trong menu Trợ giúp - đóng gói log ứng dụng "
    "thành 1 file zip để gửi khi cần hỗ trợ; dòng license đã kích hoạt giờ "
    "hiện thông tin gói thay vì bắt nhập lại key mỗi lần bấm vào; vá lỗi "
    "chữ ký cập nhật tự động không xác thực được (ảnh hưởng các bản "
    "1.0.28-1.0.30, cần cài lại thủ công 1 lần bản 1.0.31 để vá vĩnh viễn); "
    "sửa icon file PDF hiển thị sai trong Windows Explorer chế độ xem chi "
    "tiết."
)
# Release notes for the bootstrap release; keep the historical long note above
# in source for reference, but publish only the notes that describe 1.0.32.
RELEASE_NOTES = (
    "Phien ban 1.0.32: them co che cap nhat nhe B53 cho cac ban va code sau nay; "
    "cai tien icon file PDF va giao dien bo cai dat; an cua so console den cua Tesseract. "
    "Auto-OCR khi mo file tam thoi duoc tat de uu tien do on dinh trong khi tiep tuc "
    "xu ly loi vang app khi mo tai lieu."
)

REMOTE_CONFIG_PATH = "/home/hieupt/projects/3T_Reader/phase1-backend/data/admin-config.json"
LOCAL_DIR = r"C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\build\installer"
REMOTE_DOWNLOADS_DIR = "/home/hieupt/projects/3T_Reader/phase1-backend/downloads"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def deploy() -> None:
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())

    print("Connecting to 192.168.1.254:2222 (LAN direct)...")
    client.connect(
        hostname="192.168.1.254",
        port=2222,
        username="hieupt",
        password=vps_password(),
        timeout=15,
        banner_timeout=30,
        look_for_keys=False,
        allow_agent=False,
    )
    print("Connected.")

    sftp = client.open_sftp()

    files_to_upload = [
        (f"Setup_3T_Reader_v{VERSION}.exe", PUBLIC_INSTALLER_NAME),
        (f"3T_Reader_Portable_v{VERSION}.zip", PUBLIC_PORTABLE_NAME),
    ]
    for local_name, remote_name in files_to_upload:
        local_path = os.path.join(LOCAL_DIR, local_name)
        remote_path = f"{REMOTE_DOWNLOADS_DIR}/{remote_name}"
        if not os.path.exists(local_path):
            print(f"WARNING: {local_path} không tồn tại, bỏ qua.")
            continue
        print(f"Uploading {local_name} -> {remote_path} ...")
        sftp.put(local_path, remote_path)
        print(f"OK: {local_name} uploaded.")

    # Đọc config THẬT đang chạy trên VPS - chỉ ghi đè field win_*/portable_*/
    # release_notes, giữ nguyên mọi field khác (đặc biệt mac_version/mac_url).
    with sftp.open(REMOTE_CONFIG_PATH, "r") as f:
        remote_cfg = json.loads(f.read().decode("utf-8"))

    update_cfg = dict(remote_cfg.get("update", {}))
    installer_path = os.path.join(LOCAL_DIR, f"Setup_3T_Reader_v{VERSION}.exe")
    portable_path = os.path.join(LOCAL_DIR, f"3T_Reader_Portable_v{VERSION}.zip")
    installer_sha = ""
    if os.path.exists(installer_path):
        installer_sha = sha256_file(installer_path)
        update_cfg["win_version"] = VERSION
        update_cfg["win_url"] = f"{BASE_URL}/{PUBLIC_INSTALLER_NAME}"
        update_cfg["win_sha256"] = installer_sha
        update_cfg["release_notes"] = RELEASE_NOTES
    if os.path.exists(portable_path):
        update_cfg["portable_url"] = f"{BASE_URL}/{PUBLIC_PORTABLE_NAME}"
        update_cfg["portable_sha256"] = sha256_file(portable_path)

    remote_cfg["update"] = update_cfg
    cfg_str = json.dumps(remote_cfg, ensure_ascii=False, indent=2)

    local_tmp_cfg = r"C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\admin-config-update.json"
    with open(local_tmp_cfg, "w", encoding="utf-8") as f:
        f.write(cfg_str)

    print("Uploading admin-config.json ...")
    sftp.put(local_tmp_cfg, "/home/hieupt/admin-config-update.json")
    sftp.close()

    update_json_cmd = """
    sudo cp /home/hieupt/admin-config-update.json /home/hieupt/projects/3T_Reader/phase1-backend/data/admin-config.json
    sudo cp /home/hieupt/admin-config-update.json /home/hieupt/projects/3T_Reader/phase1-backend/admin-config.json
    cd /home/hieupt/projects/3T_Reader/phase1-backend/infra/backend
    sudo docker compose restart
    """
    stdin, stdout, stderr = client.exec_command(update_json_cmd, get_pty=True)
    stdin.write(vps_password() + "\n")
    stdin.flush()
    exit_code = stdout.channel.recv_exit_status()
    print(f"Config update + restart exit code: {exit_code}")

    print("Deployment completed.")
    print(f"Installer URL: {BASE_URL}/{PUBLIC_INSTALLER_NAME}")
    print(f"Installer SHA-256: {installer_sha}")

    client.close()


if __name__ == "__main__":
    deploy()
