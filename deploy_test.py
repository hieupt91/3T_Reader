import subprocess
import socket
import threading
import paramiko
import time
import sys
from vps_secret import vps_password

def forward_proc_to_sock(proc, sock):
    try:
        while True:
            data = proc.stdout.read(4096)
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

client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.RejectPolicy())

print("Connecting...")
try:
    client.connect(
        hostname="ssh.3tcomputer.com",
        username="hieupt",
        password=vps_password(),
        sock=s2,
        timeout=15
    )
    print("Connected successfully!")
    
    commands = [
        "cd /var/www/vps_reader && git pull origin release-1.0.7-baseline-ocr-ai",
        "sudo systemctl restart vps_reader"
    ]
    
    for cmd in commands:
        print(f"Running: {cmd}")
        # Note: sudo might require password or might be passwordless. If it needs password, we might need get_pty=True
        # We'll just run it. If it asks for password, we can provide it.
        stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
        time.sleep(1)
        # If it prompts for sudo password
        stdin.write(vps_password() + "\n")
        stdin.flush()
        
        out = stdout.read().decode()
        err = stderr.read().decode()
        if out: print("OUT:", out)
        if err: print("ERR:", err)
        
except Exception as e:
    print(f"Error: {e}")
finally:
    client.close()
    proc.terminate()
