import paramiko
import os
import json
import hashlib
from vps_secret import vps_password


VERSION = "1.0.18"
BASE_URL = "https://reader.3tcomputer.com/downloads"
INSTALLER_PATH = r"C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\build\installer\Setup_3T_Reader_v1.0.18.exe"
PORTABLE_PATH = r"C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\build\installer\3T_Reader_Portable_v1.0.18.zip"
PUBLIC_INSTALLER_NAME = "3TReader-1.0.18-win-r3.exe"
PUBLIC_PORTABLE_NAME = "3TReader-1.0.18-win-portable-r3.zip"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().upper()

def deploy():
    hostname = "192.168.1.254"
    port = 2222
    username = "hieupt"
    password = vps_password()
    
    print(f"Connecting to {hostname}:{port} as {username}...")
    
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    
    try:
        client.connect(
            hostname=hostname,
            port=port,
            username=username,
            password=password,
            timeout=15,
            banner_timeout=15
        )
        print("Connected successfully!")
        
        with open(r"C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\admin-config.json", "r", encoding="utf-8") as f:
            local_cfg = json.load(f)

        update_cfg = dict(local_cfg.get("update", {}))
        if os.path.exists(INSTALLER_PATH):
            update_cfg["win_version"] = VERSION
            update_cfg["win_url"] = f"{BASE_URL}/{PUBLIC_INSTALLER_NAME}"
            update_cfg["win_sha256"] = sha256_file(INSTALLER_PATH)
        if os.path.exists(PORTABLE_PATH):
            update_cfg["portable_url"] = f"{BASE_URL}/{PUBLIC_PORTABLE_NAME}"
            update_cfg["portable_sha256"] = sha256_file(PORTABLE_PATH)

        cfg_str = json.dumps(update_cfg)
        
        update_json_cmd = f"""
        cd /home/hieupt/projects/3T_Reader/phase1-backend/data
        echo '{cfg_str}' > /tmp/update_cfg.json
        jq '.update = input' admin-config.json /tmp/update_cfg.json > /tmp/tmp_admin.json
        echo {vps_password()} | sudo -S cp /tmp/tmp_admin.json admin-config.json
        echo {vps_password()} | sudo -S chmod 666 admin-config.json
        """
        stdin, stdout, stderr = client.exec_command(update_json_cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        if out: print(out)
        if err: print(err)
        
        print("Updated admin-config.json on VPS.")
        
        client.close()
        print("VPS config update completed successfully!")
        
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    deploy()
