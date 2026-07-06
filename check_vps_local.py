import paramiko
from vps_secret import vps_password

def run():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect('192.168.1.254', 2222, 'hieupt', vps_password())
        
        stdin, stdout, stderr = client.exec_command('cat /home/hieupt/projects/3T_Reader/phase1-backend/server/license-api/app/config.py')
        print(stdout.read().decode())
        
        client.close()
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    run()
