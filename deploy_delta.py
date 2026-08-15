"""B53: dẩy 1 code package delta (chỉ các file Python thay đổi, không đụng
bootstrap bất biến) lên VPS - dùng cho các bản vá thường sau bản nền 1.0.34,
không cần build lại installer đầy đủ. Xem scripts/build_code_package.py để
đóng gói code package trước khi chạy script này.

Cách dùng (PowerShell):
    $env:THREET_VPS_PASSWORD = "..."
    $env:CODE_PACKAGE_LOCAL = "đường dẫn tới code_package.zip"
    $env:CODE_PACKAGE_VERSION = "1.0.34.1"
    $env:CODE_PACKAGE_NOTES = "Mô tả thay đổi cho người dùng"
    python deploy_delta.py
"""
import hashlib
import json
import os
import sys

import paramiko

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from vps_secret import vps_password

CODE_PACKAGE_LOCAL = os.environ["CODE_PACKAGE_LOCAL"]
CODE_PACKAGE_VERSION = os.environ["CODE_PACKAGE_VERSION"]
CODE_PACKAGE_NOTES = os.environ["CODE_PACKAGE_NOTES"]
CODE_PACKAGE_BASE_VERSION = os.environ.get("CODE_PACKAGE_BASE_VERSION", "base-1.1")
REMOTE_CONFIG_PATH = "/home/hieupt/projects/3T_Reader/phase1-backend/data/admin-config.json"
REMOTE_DOWNLOADS_DIR = "/home/hieupt/projects/3T_Reader/phase1-backend/downloads"
BASE_URL = "https://reader.3tcomputer.com/downloads"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(
        hostname="192.168.1.254", port=2222, username="hieupt",
        password=vps_password(), timeout=15, banner_timeout=30,
        look_for_keys=False, allow_agent=False,
    )
    print("Connected.")

    sftp = client.open_sftp()
    remote_name = f"code_package_{CODE_PACKAGE_VERSION}.zip"
    remote_path = f"{REMOTE_DOWNLOADS_DIR}/{remote_name}"
    sftp.put(CODE_PACKAGE_LOCAL, remote_path)
    code_sha = sha256_file(CODE_PACKAGE_LOCAL)
    print(f"Uploaded: {remote_path}")
    print(f"SHA-256: {code_sha}")

    with sftp.open(REMOTE_CONFIG_PATH, "r") as f:
        remote_cfg = json.loads(f.read().decode("utf-8"))

    update_cfg = dict(remote_cfg.get("update", {}))
    update_cfg["win_version"] = CODE_PACKAGE_VERSION
    update_cfg["win_code_url"] = f"{BASE_URL}/{remote_name}"
    update_cfg["win_code_sha256"] = code_sha
    update_cfg["win_base_version"] = CODE_PACKAGE_BASE_VERSION
    update_cfg["delta_enabled"] = True
    update_cfg["release_notes"] = CODE_PACKAGE_NOTES
    remote_cfg["update"] = update_cfg
    cfg_str = json.dumps(remote_cfg, ensure_ascii=False, indent=2)

    local_tmp_cfg = r"C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\admin-config-delta.json"
    with open(local_tmp_cfg, "w", encoding="utf-8") as f:
        f.write(cfg_str)
    sftp.put(local_tmp_cfg, "/home/hieupt/admin-config-delta.json")
    sftp.close()
    os.remove(local_tmp_cfg)

    cmd = """
    sudo cp /home/hieupt/admin-config-delta.json /home/hieupt/projects/3T_Reader/phase1-backend/data/admin-config.json
    sudo cp /home/hieupt/admin-config-delta.json /home/hieupt/projects/3T_Reader/phase1-backend/admin-config.json
    cd /home/hieupt/projects/3T_Reader/phase1-backend/infra/backend
    sudo docker compose restart
    """
    stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
    stdin.write(vps_password() + "\n")
    stdin.flush()
    exit_code = stdout.channel.recv_exit_status()
    print(f"Config update + restart exit code: {exit_code}")
    client.close()


if __name__ == "__main__":
    main()
