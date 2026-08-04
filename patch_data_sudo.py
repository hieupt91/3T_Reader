import paramiko
import json
from vps_secret import vps_password

def run():
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    try:
        client.connect('192.168.1.254', 2222, 'hieupt', vps_password())
        
        # Upload a python script to do the patch
        patcher = """import json
with open('/home/hieupt/projects/3T_Reader/phase1-backend/data/license-api-state.json', 'r') as f:
    data = json.load(f)
changed = False
for key, payload in data.get('licenses', {}).items():
    if "plan" not in payload:
        if key.startswith("3TR-E-"):
            payload["plan"] = "enterprise"
            changed = True
        elif key.startswith("3TR-B-"):
            payload["plan"] = "basic"
            changed = True
        elif key.startswith("THREET-DEMO-ENTERPRISE"):
            payload["plan"] = "enterprise"
            changed = True
        else:
            payload["plan"] = "personal"
            changed = True
if changed:
    with open('/home/hieupt/projects/3T_Reader/phase1-backend/data/license-api-state.json', 'w') as f:
        json.dump(data, f, indent=2, sort_keys=True)
    print("Patched!")
else:
    print("No missing plans.")
"""
        sftp = client.open_sftp()
        with sftp.file('/home/hieupt/patch_json.py', 'w') as f:
            f.write(patcher.encode('utf-8'))
        sftp.close()
        
        # Run with sudo
        stdin, stdout, stderr = client.exec_command('sudo -S python3 /home/hieupt/patch_json.py', get_pty=True)
        stdin.write(vps_password() + "\n")
        stdin.flush()
        print("Patcher output:", stdout.read().decode())
        
        # Restart backend
        stdin, stdout, stderr = client.exec_command('cd /home/hieupt/projects/3T_Reader/phase1-backend/infra/backend && docker compose restart license-api', get_pty=True)
        stdin.write(vps_password() + "\n")
        stdin.flush()
        print("Restart output:", stdout.read().decode())
        
        client.close()
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    run()
