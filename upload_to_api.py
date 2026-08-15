import requests
import json
import hashlib
import sys
import os
from vps_secret import vps_password

BASE_URL = "https://reader.3tcomputer.com"
ADMIN_PASSWORD = vps_password()
INSTALLER_PATH = r"C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\build\installer\Setup_3T_Reader_v1.0.22.exe"
PORTABLE_PATH = r"C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\build\installer\3T_Reader_Portable_v1.0.22.zip"
VERSION = "1.0.22"

def main():
    print("Logging in to admin API...")
    res = requests.post(f"{BASE_URL}/api/admin/login", json={"password": ADMIN_PASSWORD})
    if res.status_code != 200:
        print(f"Login failed: {res.text.encode('utf-8')}")
        sys.exit(1)
    
    token = res.json().get("token")
    headers = {"Authorization": f"Bearer {token}"}
    
    print("Uploading Installer...")
    with open(INSTALLER_PATH, "rb") as f:
        res = requests.post(
            f"{BASE_URL}/api/admin/upload-release",
            headers=headers,
            data={"platform": "win", "version": VERSION},
            files={"file": ("Setup_3T_Reader_v1.0.22.exe", f, "application/octet-stream")}
        )
    if res.status_code != 200:
        print(f"Installer upload failed: {res.text.encode('utf-8')}")
        sys.exit(1)
        
    installer_data = res.json()
    print(f"Installer Upload OK: {installer_data}")

    print("Uploading Portable ZIP...")
    with open(PORTABLE_PATH, "rb") as f:
        res2 = requests.post(
            f"{BASE_URL}/api/admin/upload-release",
            headers=headers,
            data={"platform": "win-portable", "version": VERSION},
            files={"file": ("3T_Reader_Portable_v1.0.22.zip", f, "application/zip")}
        )
    if res2.status_code != 200:
        print(f"Portable upload failed: {res2.text.encode('utf-8')}")
        sys.exit(1)
    portable_data = res2.json()
    print(f"Portable Upload OK: {portable_data}")

    cfg_res = requests.get(f"{BASE_URL}/api/admin/update-config", headers=headers)
    if cfg_res.status_code != 200:
        print(f"Read config failed: {cfg_res.text.encode('utf-8')}")
        sys.exit(1)
    cfg = cfg_res.json()

    print("Fixing Update Config...")
    cfg["win_version"] = VERSION
    cfg["win_url"] = installer_data["download_url"]
    cfg["win_sha256"] = installer_data["sha256"]
    cfg["portable_url"] = portable_data["download_url"]
    cfg["portable_sha256"] = portable_data["sha256"]
    
    res = requests.post(
        f"{BASE_URL}/api/admin/update-config",
        headers=headers,
        json=cfg
    )
    if res.status_code != 200:
        print(f"Config update failed: {res.text.encode('utf-8')}")
        sys.exit(1)
        
    print("Deployment Config Updated Successfully!")

if __name__ == '__main__':
    main()
