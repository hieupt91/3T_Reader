import socket
import threading
import subprocess
import time
import paramiko
import os
import json
import hashlib

VERSION = "1.0.24"
BASE_URL = "https://reader.3tcomputer.com/downloads"
PUBLIC_INSTALLER_NAME = "3TReader-1.0.24-win-r3.exe"
PUBLIC_PORTABLE_NAME = "3TReader-1.0.24-win-portable-r3.zip"

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
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print("Connecting to VPS via cloudflared...")
    
    try:
        client.connect(
            hostname="ssh.3tcomputer.com",
            username="hieupt",
            password="Congnghe3t",
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
            ("Setup_3T_Reader_v1.0.24.exe", PUBLIC_INSTALLER_NAME),
            ("3T_Reader_Portable_v1.0.24.zip", PUBLIC_PORTABLE_NAME)
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
        
        print("Updating VPS docker-compose.yml if needed...")
        update_cmd = """
        cd /home/hieupt/projects/3T_Reader/phase1-backend
        if [ -f docker-compose.yml ]; then
            sed -i 's/1.0.22/1.0.24/g' docker-compose.yml
            docker compose restart
        else
            echo "docker-compose.yml not found, skipping restart."
        fi
        """
        stdin, stdout, stderr = client.exec_command(update_cmd)
        print(stdout.read().decode())
        print(stderr.read().decode())
        
        with open(r"C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\admin-config.json", "r", encoding="utf-8") as f:
            local_cfg = json.load(f)

        update_cfg = dict(local_cfg.get("update", {}))
        installer_path = os.path.join(local_dir, "Setup_3T_Reader_v1.0.24.exe")
        portable_path = os.path.join(local_dir, "3T_Reader_Portable_v1.0.24.zip")
        if os.path.exists(installer_path):
            update_cfg["win_version"] = VERSION
            update_cfg["win_url"] = f"{BASE_URL}/{PUBLIC_INSTALLER_NAME}"
            update_cfg["win_sha256"] = sha256_file(installer_path)
            update_cfg["release_notes"] = "Phiên bản 1.0.24: Hoàn thiện Phase 7-9, tối ưu hiệu suất tốc độ cao, hỗ trợ Edit Text trực tiếp và OCR ổn định."
        if os.path.exists(portable_path):
            update_cfg["portable_url"] = f"{BASE_URL}/{PUBLIC_PORTABLE_NAME}"
            update_cfg["portable_sha256"] = sha256_file(portable_path)
            
        local_cfg["update"] = update_cfg

        cfg_str = json.dumps(local_cfg, ensure_ascii=False, indent=2)
        
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
        stdin.write("Congnghe3t\n")
        stdin.flush()
        # Do not print stdout/stderr because of cp1252 charmap encoding errors
        
        print("Updated admin-config.json on VPS.")
        
        client.close()
        print("Deployment completed successfully!")
        
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    deploy()
