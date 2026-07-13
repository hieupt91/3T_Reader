import paramiko
from vps_secret import vps_password

def run():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect('192.168.1.254', 2222, 'hieupt', vps_password())
        
        # Read state_store.py
        target_file = "/home/hieupt/projects/3T_Reader/phase1-backend/server/license-api/app/services/state_store.py"
        sftp = client.open_sftp()
        with sftp.file(target_file, 'r') as f:
            content = f.read().decode('utf-8')
            
        # Patch load_licenses
        content = content.replace(
            'seat_limit=int(payload["seat_limit"]),',
            'seat_limit=int(payload["seat_limit"]),\n                    plan=payload.get("plan", "personal"),'
        )
        
        # Patch save_licenses
        content = content.replace(
            '"seat_limit": record.seat_limit,',
            '"seat_limit": record.seat_limit,\n                        "plan": getattr(record, "plan", "personal"),'
        )
        
        # Write back
        with sftp.file(target_file, 'w') as f:
            f.write(content.encode('utf-8'))
            
        print("Patched state_store.py successfully!")
        
        # Restart backend
        stdin, stdout, stderr = client.exec_command('cd /home/hieupt/projects/3T_Reader/phase1-backend/infra/backend && docker compose restart license-api')
        print(stdout.read().decode())
        print(stderr.read().decode())
        
        sftp.close()
        client.close()
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    run()
