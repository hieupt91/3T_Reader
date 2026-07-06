import os
import sys
import shutil
import subprocess
from pathlib import Path

def main():
    print("=== 3T READER SECURE BUILD PIPELINE ===")
    print("1. Preparing secure build environment...")
    
    # We will compile the sensitive files in-place (or rather, we backup, compile, and restore)
    # But to be safe, we'll create a temporary build directory
    src_dir = Path(os.getcwd())
    build_dir = src_dir / "build_secure_tmp"
    
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)
        
    os.makedirs(build_dir, exist_ok=True)
    
    # Copy essential directories to build_secure_tmp
    build_items = ["app", "assets", "core", "packages", "styles", "third_party", "main.py", "3T_Reader.spec"]
    if (src_dir / "piper_bin").exists():
        build_items.append("piper_bin")
    if (src_dir / "venv_piper").exists():
        build_items.append("venv_piper")

    for item in build_items:
        src_item = src_dir / item
        dst_item = build_dir / item
        if src_item.is_dir():
            shutil.copytree(src_item, dst_item)
        elif src_item.is_file():
            shutil.copy2(src_item, dst_item)
            
    print("2. Obfuscating sensitive modules using Nuitka (C-Compilation)...")
    sensitive_files = [
        "packages/license_client/vps_client.py",
        "app/window.py",
        "app/actions/pages.py",
        "app/actions/annotate.py"
    ]
    
    python_exe = sys.executable
    
    for rel_path in sensitive_files:
        file_path = build_dir / rel_path
        if not file_path.exists():
            continue
            
        print(f" -> Compiling {rel_path} to Native C extension...")
        cmd = [
            python_exe, "-m", "nuitka", "--module", 
            str(file_path),
            "--output-dir=" + str(file_path.parent)
        ]
        
        # Run Nuitka
        try:
            subprocess.run(cmd, cwd=build_dir, check=True)
        except subprocess.CalledProcessError as exc:
            print(f" -> WARNING: Nuitka failed for {rel_path} ({exc}). Keeping source module and continuing.")
            continue

        # Nuitka creates a .pyd file and a .build folder.
        # Delete the original .py file so PyInstaller prefers the native module.
        os.remove(file_path)
        print(f" -> Successfully secured {rel_path}")

    print("3. Building EXE with PyInstaller...")
    # Now run PyInstaller inside the build_dir
    pyinstaller_cmd = [
        python_exe, "-m", "PyInstaller", "--noconfirm", "3T_Reader.spec"
    ]
    subprocess.run(pyinstaller_cmd, cwd=build_dir, check=True)
    
    print("4. Copying secured EXE to dist/...")
    dist_dir = src_dir / "dist"
    os.makedirs(dist_dir, exist_ok=True)
    
    # The output is in build_secure_tmp/dist/3T_Reader
    # Note: 3T_Reader.spec produces a directory by default. 
    # If it produces an EXE, we copy the EXE.
    built_dist = build_dir / "dist" / "3T_Reader"
    target_dist = dist_dir / "3T_Reader_Secure"
    
    if target_dist.exists():
        shutil.rmtree(target_dist, ignore_errors=True)
        
    shutil.copytree(built_dist, target_dist)

    print("5. Cleaning up temporary build directory...")
    shutil.rmtree(build_dir, ignore_errors=True)

    print(f"=== BUILD COMPLETE! SECURE APP LOCATED AT: {target_dist} ===")

if __name__ == "__main__":
    main()
