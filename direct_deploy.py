import paramiko
import os
from vps_secret import vps_password

def deploy():
    hostname = "192.168.1.254"
    port = 2222
    username = "hieupt"
    password = vps_password()
    
    print(f"Connecting to {hostname}:{port} as {username}...")
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
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
        remote_dir = "/var/www/vps_reader/downloads"
        
        files_to_upload = [
            ("Setup_3T_Reader_v1.0.18.exe", "3TReader-1.0.18-win.exe"),
            ("3T_Reader_Portable_v1.0.18.zip", "3TReader-1.0.18-win-portable.zip")
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
        
        # Update docker-compose and restart if needed, or just let API pick it up?
        # Let's see if we need to update any config on VPS
        # The user said "của vps nhớ check kỹ trong vps nhé"
        print("Checking VPS docker-compose.yml...")
        stdin, stdout, stderr = client.exec_command('cd /var/www/vps_reader && cat docker-compose.yml')
        compose_content = stdout.read().decode()
        if "1.0.18" not in compose_content:
            print("Updating docker-compose.yml with version 1.0.18...")
            update_cmd = """
            cd /var/www/vps_reader &&
            sed -i 's/1.0.17/1.0.18/g' docker-compose.yml &&
            docker compose restart license-api
            """
            stdin, stdout, stderr = client.exec_command(update_cmd)
            print(stdout.read().decode())
            print(stderr.read().decode())
            print("Updated and restarted license-api on VPS.")
        else:
            print("VPS already has 1.0.18 in docker-compose.yml.")
            
        client.close()
        print("Deployment completed successfully!")
        
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    deploy()
