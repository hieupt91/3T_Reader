import paramiko
from vps_secret import vps_password

def test_ssh():
    print("Setting up proxy command...")
    # Wrap in double quotes for cmd.exe
    proxy_cmd = r'""C:\Program Files (x86)\cloudflared\cloudflared.exe" access ssh --hostname ssh.3tcomputer.com"'
    sock = paramiko.ProxyCommand(proxy_cmd)
    
    print("Connecting...")
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    
    try:
        client.connect(
            hostname='ssh.3tcomputer.com',
            username='hieupt',
            password=vps_password(),
            sock=sock,
            timeout=15,
            banner_timeout=15
        )
        print('Connected successfully!')
        
        stdin, stdout, stderr = client.exec_command('ls -la /var/www/vps_reader/downloads')
        print(stdout.read().decode())
        
        client.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_ssh()
