import paramiko
import json
from vps_secret import vps_password

def run():
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    try:
        client.connect('192.168.1.254', 2222, 'hieupt', vps_password())
        
        target_file = "/home/hieupt/projects/3T_Reader/phase1-backend/data/license-api-state.json"
        
        sftp = client.open_sftp()
        try:
            with sftp.file(target_file, 'r') as f:
                content = f.read().decode('utf-8')
                
            data = json.loads(content)
            changed = False
            for key, payload in data.get('licenses', {}).items():
                if "plan" not in payload:
                    # Infer from prefix
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
                with sftp.file(target_file, 'w') as f:
                    f.write(json.dumps(data, indent=2, sort_keys=True).encode('utf-8'))
                print("Patched existing data/license-api-state.json plans successfully!")
            else:
                print("No missing plans found.")
                
            # Restart backend again to load the new JSON
            stdin, stdout, stderr = client.exec_command('cd /home/hieupt/projects/3T_Reader/phase1-backend/infra/backend && docker compose restart license-api')
            print("Restarted backend:", stdout.read().decode())
                
        except Exception as e:
            print("SFTP Error:", e)
            
        sftp.close()
        client.close()
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    run()
