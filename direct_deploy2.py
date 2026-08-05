import paramiko
import os
import json
import hashlib
from vps_secret import vps_password


VERSION = "1.0.18"
BASE_URL = "https://reader.3tcomputer.com/downloads"
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
        
        sftp = client.open_sftp()
        
        # Paths
        local_dir = r"C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\build\installer"
        remote_dir = "/home/hieupt/projects/3T_Reader/phase1-backend/downloads"
        
        files_to_upload = [
            ("Setup_3T_Reader_v1.0.18.exe", PUBLIC_INSTALLER_NAME),
            ("3T_Reader_Portable_v1.0.18.zip", PUBLIC_PORTABLE_NAME)
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
        
        sftp.close()
        
        print("Updating VPS docker-compose.yml if needed...")
        update_cmd = """
        cd /home/hieupt/projects/3T_Reader/phase1-backend
        if [ -f docker-compose.yml ]; then
            sed -i 's/1.0.17/1.0.18/g' docker-compose.yml
            docker compose restart
        else
            echo "docker-compose.yml not found, skipping restart."
        fi
        """
        stdin, stdout, stderr = client.exec_command(update_cmd)
        print(stdout.read().decode())
        print(stderr.read().decode())
        
        # Now update the admin-config.json
        with open(r"C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\admin-config.json", "r", encoding="utf-8") as f:
            local_cfg = json.load(f)

        update_cfg = dict(local_cfg.get("update", {}))
        installer_path = os.path.join(local_dir, "Setup_3T_Reader_v1.0.18.exe")
        portable_path = os.path.join(local_dir, "3T_Reader_Portable_v1.0.18.zip")
        if os.path.exists(installer_path):
            update_cfg["win_version"] = VERSION
            update_cfg["win_url"] = f"{BASE_URL}/{PUBLIC_INSTALLER_NAME}"
            update_cfg["win_sha256"] = sha256_file(installer_path)
        if os.path.exists(portable_path):
            update_cfg["portable_url"] = f"{BASE_URL}/{PUBLIC_PORTABLE_NAME}"
            update_cfg["portable_sha256"] = sha256_file(portable_path)

        cfg_str = json.dumps(update_cfg)
        
        update_json_cmd = f"""
        cd /home/hieupt/projects/3T_Reader/phase1-backend/data
        # Update admin-config.json using jq
        jq '.update = {cfg_str}' admin-config.json > tmp.json && mv tmp.json admin-config.json
        """
        stdin, stdout, stderr = client.exec_command(update_json_cmd)
        print(stdout.read().decode())
        print(stderr.read().decode())
        
        print("Updated admin-config.json on VPS.")
        
        client.close()
        print("Deployment completed successfully!")
        
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    deploy()
