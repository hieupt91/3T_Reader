import socket
import threading
import subprocess
import time
import paramiko
import os

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
        
        cmd = "cat /home/hieupt/projects/3T_Reader/phase1-backend/admin-config.json"
        print(f"--- {cmd} ---")
        stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
        time.sleep(1)
        stdin.write("Congnghe3t\n")
        stdin.flush()
        print(stdout.read().decode())
        print(stderr.read().decode())
            
        client.close()
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    deploy()
