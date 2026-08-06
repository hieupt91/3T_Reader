import socket
import threading
import subprocess
import time
import paramiko
import os
import json
import hashlib
from vps_secret import vps_password
from app.version import APP_VERSION

VERSION = APP_VERSION
BASE_URL = "https://reader.3tcomputer.com/downloads"
PUBLIC_INSTALLER_NAME = f"3TReader-{VERSION}-win-r3.exe"
PUBLIC_PORTABLE_NAME = f"3TReader-{VERSION}-win-portable-r3.zip"
RELEASE_NOTES = (
    "Phiên bản 1.0.28: Thêm Chuyển/Nhận tài liệu trực tiếp qua thiết bị "
    "ScanDoc (P2P, không qua máy chủ); sửa cảnh báo sai \"Chưa lưu xong "
    "chú thích\" khi chỉ đọc tài liệu; sửa vệt đuôi chữ bị cắt cụt khi "
    "Sửa text gốc."
)
REMOTE_CONFIG_PATH = "/home/hieupt/projects/3T_Reader/phase1-backend/data/admin-config.json"

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().upper()

def forward_proc_to_sock(proc, sock):
    try:
        while True:
            data = proc.stdout.read1(4096)
            if not data:
                break
            sock.sendall(data)
    except Exception as e:
        pass

def forward_sock_to_proc(sock, proc):
    try:
        while True:
            data = sock.recv(4096)
            if not data:
                break
            proc.stdin.write(data)
            proc.stdin.flush()
    except Exception as e:
        pass

def deploy():
    s1, s2 = socket.socketpair()

    proc = subprocess.Popen(
        [r"C:\Program Files (x86)\cloudflared\cloudflared.exe", "access", "ssh", "--hostname", "ssh.3tcomputer.com"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )

    t1 = threading.Thread(target=forward_proc_to_sock, args=(proc, s1), daemon=True)
    t2 = threading.Thread(target=forward_sock_to_proc, args=(s1, proc), daemon=True)
    t1.start()
    t2.start()

    time.sleep(5)

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())

    print("Connecting to VPS via cloudflared...")
    
    try:
        client.connect(
            hostname="ssh.3tcomputer.com",
            username="hieupt",
            password=vps_password(),
            sock=s2,
            timeout=15,
            banner_timeout=200,
            look_for_keys=False,
            allow_agent=False
        )
        print("Connected successfully!")
        
        sftp = client.open_sftp()
        
        local_dir = r"C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\build\installer"
        remote_dir = "/home/hieupt/projects/3T_Reader/phase1-backend/downloads"
        
        files_to_upload = [
            (f"Setup_3T_Reader_v{VERSION}.exe", PUBLIC_INSTALLER_NAME),
            (f"3T_Reader_Portable_v{VERSION}.zip", PUBLIC_PORTABLE_NAME)
        ]
        
        for local_name, remote_name in files_to_upload:
            local_path = os.path.join(local_dir, local_name)
            remote_path = f"{remote_dir}/{remote_name}"
            
            if os.path.exists(local_path):
                print(f"Uploading {local_name} -> {remote_path}...")
                sftp.put(local_path, remote_path)
                print(f"Success: {local_name} uploaded.")
            else:
                print(f"Warning: {local_path} does not exist.")
        
        # sftp.close()

        # Đọc config THẬT đang chạy trên VPS làm nền - chỉ ghi đè đúng các
        # field win_*/portable_*/release_notes bên dưới, giữ nguyên mọi
        # field khác (đặc biệt mac_version/mac_url) để không đè nhầm dữ
        # liệu Mac đang chạy thật bằng giá trị cũ/đoán mò.
        with client.open_sftp().open(REMOTE_CONFIG_PATH, "r") as f:
            remote_cfg = json.loads(f.read().decode("utf-8"))

        update_cfg = dict(remote_cfg.get("update", {}))
        installer_path = os.path.join(local_dir, f"Setup_3T_Reader_v{VERSION}.exe")
        portable_path = os.path.join(local_dir, f"3T_Reader_Portable_v{VERSION}.zip")
        if os.path.exists(installer_path):
            update_cfg["win_version"] = VERSION
            update_cfg["win_url"] = f"{BASE_URL}/{PUBLIC_INSTALLER_NAME}"
            update_cfg["win_sha256"] = sha256_file(installer_path)
            update_cfg["release_notes"] = RELEASE_NOTES
        if os.path.exists(portable_path):
            update_cfg["portable_url"] = f"{BASE_URL}/{PUBLIC_PORTABLE_NAME}"
            update_cfg["portable_sha256"] = sha256_file(portable_path)

        remote_cfg["update"] = update_cfg

        cfg_str = json.dumps(remote_cfg, ensure_ascii=False, indent=2)
        
        with open(r"C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\admin-config-update.json", "w", encoding="utf-8") as f:
            f.write(cfg_str)
            
        print("Uploading admin-config.json...")
        sftp.put(r"C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\admin-config-update.json", "/home/hieupt/admin-config-update.json")
        
        update_json_cmd = """
        sudo cp /home/hieupt/admin-config-update.json /home/hieupt/projects/3T_Reader/phase1-backend/data/admin-config.json
        sudo cp /home/hieupt/admin-config-update.json /home/hieupt/projects/3T_Reader/phase1-backend/admin-config.json
        cd /home/hieupt/projects/3T_Reader/phase1-backend/infra/backend
        sudo docker compose restart
        """
        stdin, stdout, stderr = client.exec_command(update_json_cmd, get_pty=True)
        time.sleep(1)
        stdin.write(vps_password() + "\n")
        stdin.flush()
        # Do not print stdout/stderr because of cp1252 charmap encoding errors
        
        print("Updated admin-config.json on VPS.")
        
        client.close()
        print("Deployment completed successfully!")
        
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    deploy()
