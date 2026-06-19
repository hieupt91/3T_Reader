import subprocess
import socket
import threading
import paramiko
import time
import socket
import threading
import subprocess
import time

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

def upload_files():
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

    print("Connecting via cloudflared socketpair...")

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
        print("Connected successfully!")
        
        # We need to use sudo on the VPS to write to /var/www/vps_reader/downloads/
        # Wait, how about we upload to ~ first, then move them using sudo?
        
        print("Executing commands to update config...")
        commands = [
            # Run a small python script on the VPS to update admin-config.json
            """sudo python3 -c '
import json
import hashlib

def sha256_file(path):
    m = hashlib.sha256()
    with open(path, "rb") as f:
        m.update(f.read())
    return m.hexdigest()

conf_path = "/var/data/vps_reader/admin-config.json"
try:
    with open(conf_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
except Exception:
    cfg = {"update": {}}

cfg.setdefault("update", {})
cfg["update"]["win_version"] = "1.0.21"
cfg["update"]["win_url"] = "https://reader.3tcomputer.com/downloads/3TReader-1.0.21-win.exe"
cfg["update"]["win_sha256"] = sha256_file("/var/www/vps_reader/downloads/3TReader-1.0.21-win.exe")
cfg["update"]["portable_url"] = "https://reader.3tcomputer.com/downloads/3TReader-1.0.21-win-portable.zip"
cfg["update"]["portable_sha256"] = sha256_file("/var/www/vps_reader/downloads/3TReader-1.0.21-win-portable.zip")
cfg["update"]["release_notes"] = "Phiên bản 1.0.21: Tối ưu khởi động và nạp PDF cực nhanh. Nâng cấp Lazy Load."

with open(conf_path, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
'""",
            "sudo systemctl restart vps_reader"
        ]

        for cmd in commands:
            print("Running command...")
            stdin, stdout, stderr = client.exec_command(cmd.encode("utf-8"), get_pty=True)
            time.sleep(1)
            stdin.write("Congnghe3t\n")
            stdin.flush()
            out = stdout.read().decode("utf-8", "ignore")
            err = stderr.read().decode("utf-8", "ignore")
            if out: print("OUT:", out)
            if err: print("ERR:", err)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()
        proc.terminate()

if __name__ == "__main__":
    upload_files()
