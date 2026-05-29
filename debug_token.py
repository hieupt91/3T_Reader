#!/usr/bin/env python3
"""Debug script: kiểm tra USB token PKCS#11 trên macOS."""
import os, subprocess
from pathlib import Path

CANDIDATES = [
    "viettel-ca_v6.dylib", "viettel-ca_v5.dylib", "viettel-ca.dylib",
    "ViettelCA.dylib", "ViettelPKCS11.dylib",
    "eps2003csp11.dylib", "vnpt_ca_pkcs11.dylib",
    "FPT_Token.dylib", "BkavCAPKCS11.dylib",
    "eTPKCS11.dylib", "opensc-pkcs11.so", "opensc-pkcs11.dylib",
]
SEARCH_DIRS = [
    "/usr/lib", "/usr/local/lib", "/usr/lib/pkcs11",
    "/usr/local/lib/pkcs11", "/opt/homebrew/lib",
    str(Path.home() / "Library" / "PKCS11"),
    "/Library/Security/tokend",
    "/Library/Internet Plug-Ins",
    # Viettel CA v6 thường cài ở đây:
    "/Applications/Viettel-CA Token Manager V6.0.app/Contents/MacOS",
    "/Applications/Viettel-CA Token Manager V6.0.app/Contents/Resources",
]

print("=" * 60)
print("BƯỚC 1: Tìm file .dylib trên máy")
print("=" * 60)
found_libs = []
for d in SEARCH_DIRS:
    for name in CANDIDATES:
        p = os.path.join(d, name)
        if os.path.exists(p):
            print(f"  ✅ TÌM THẤY: {p}")
            found_libs.append(p)

# Tìm thêm bằng find
print("\nTìm thêm bằng 'find'...")
for name in ["viettel-ca*.dylib", "ViettelCA*.dylib", "eps2003*.dylib"]:
    try:
        r = subprocess.run(
            ["find", "/usr", "/opt", "/Library", "/Applications", "-name", name, "-maxdepth", "8"],
            capture_output=True, text=True, timeout=10
        )
        for line in r.stdout.strip().splitlines():
            if line and line not in found_libs:
                print(f"  ✅ find: {line}")
                found_libs.append(line)
    except Exception as e:
        print(f"  find error: {e}")

if not found_libs:
    print("  ❌ KHÔNG tìm thấy file .dylib nào!")
    print("     → Driver chưa cài, hoặc cài ở đường dẫn khác.")

print("\n" + "=" * 60)
print("BƯỚC 2: Kiểm tra PCSC / smart card readers")
print("=" * 60)
try:
    r = subprocess.run(["pcsctest"], capture_output=True, text=True, timeout=5)
    print(r.stdout[:500] or "(no output)")
except FileNotFoundError:
    print("  pcsctest không có sẵn (bình thường)")

try:
    r = subprocess.run(["system_profiler", "SPSmartCardsDataType"], capture_output=True, text=True, timeout=10)
    out = r.stdout.strip()
    print(out[:1000] if out else "  (không có smart card nào được nhận diện)")
except Exception as e:
    print(f"  Lỗi: {e}")

print("\n" + "=" * 60)
print("BƯỚC 3: Kiểm tra CTK extension")
print("=" * 60)
try:
    r = subprocess.run(["pluginkit", "-m", "-v"], capture_output=True, text=True, timeout=10)
    for line in r.stdout.splitlines():
        if "ftsafe" in line.lower() or "viettel" in line.lower() or "smartcard" in line.lower():
            print(f"  {line}")
    if not any("ftsafe" in l.lower() or "viettel" in l.lower() for l in r.stdout.splitlines()):
        print("  (Không thấy extension FeiTian/Viettel)")
except Exception as e:
    print(f"  Lỗi: {e}")

print("\n" + "=" * 60)
print("BƯỚC 4: Thử load PKCS#11 library")
print("=" * 60)
if not found_libs:
    print("  (Bỏ qua — không tìm thấy lib nào)")
else:
    try:
        import pkcs11 as p11
        for lib_path in found_libs:
            print(f"\n  Thử: {lib_path}")
            try:
                lib = p11.lib(lib_path)
                tokens = list(lib.get_tokens())
                if tokens:
                    print(f"  ✅ THÀNH CÔNG! Tìm thấy {len(tokens)} token:")
                    for t in tokens:
                        print(f"     - {t.label!r} | {t.manufacturer_id!r}")
                else:
                    print(f"  ⚠️  Lib load OK nhưng 0 token (USB chưa cắm hoặc Token Manager chưa chạy)")
            except Exception as exc:
                print(f"  ❌ Lỗi: {exc}")
    except ImportError:
        print("  ❌ python-pkcs11 chưa cài (pip install python-pkcs11)")

print("\n" + "=" * 60)
print("BƯỚC 5: Token Manager đang chạy?")
print("=" * 60)
try:
    r = subprocess.run(["pgrep", "-fl", "Viettel"], capture_output=True, text=True)
    if r.stdout.strip():
        print(f"  ✅ Đang chạy: {r.stdout.strip()}")
    else:
        print("  ❌ Token Manager KHÔNG chạy")
        print("     → Mở: /Applications/Viettel-CA Token Manager V6.0.app")
except Exception as e:
    print(f"  Lỗi: {e}")

print("\nXong!")
