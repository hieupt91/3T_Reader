import os
import sys
import subprocess
import io

def log(msg):
    print(f"[*] {msg}")

def update_version():
    log("Updating write_index.py to version 1.0.22")
    index_path = r"C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\write_index.py"
    with io.open(index_path, 'rb') as f:
        content = f.read()
    content = content.replace(b"1.0.20", b"1.0.22")
    content = content.replace(b"1.0.18", b"1.0.22")
    content = content.replace(b"1.0.17", b"1.0.22")
    with io.open(index_path, 'wb') as f:
        f.write(content)

def run_build():
    log("Running build_secure.py...")
    python_exe = r"C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\.venv313\Scripts\python.exe"
    subprocess.run([python_exe, "build_secure.py"], check=True)

def run_inno():
    log("Running Inno Setup compiler...")
    # Assuming standard installation path
    iscc_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe"
    ]
    iscc = None
    for p in iscc_paths:
        if os.path.exists(p):
            iscc = p
            break
    if not iscc:
        log("ISCC.exe not found! Please compile installer_script.iss manually.")
        return
    subprocess.run([iscc, "installer_script.iss"], check=True)

def upload_vps():
    log("Deploying to VPS... (Calling deploy_test.py or pushing code)")
    python_exe = r"C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\.venv313\Scripts\python.exe"
    if os.path.exists("deploy_test.py"):
        subprocess.run([python_exe, "deploy_test.py"], check=True)

def main():
    try:
        update_version()
        run_build()
        run_inno()
        upload_vps()
        log("ALL TASKS COMPLETED SUCCESSFULLY!")
    except Exception as e:
        log(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
