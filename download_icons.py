# download_icons.py - chạy: python download_icons.py
import urllib.request, os

os.makedirs("assets/icons", exist_ok=True)

FIXES = {
    "fit_page.svg": "Fit%20Page%20Height/SVG/ic_fluent_fit_page_height_24_regular.svg",
    "usb.svg":      "Usb%20Stick/SVG/ic_fluent_usb_stick_24_regular.svg",
}

BASE = "https://raw.githubusercontent.com/microsoft/fluentui-system-icons/main/assets"
ICONS = {
    "folder_open.svg":   "Folder%20Open/SVG/ic_fluent_folder_open_24_regular.svg",
    "history.svg":       "History/SVG/ic_fluent_history_24_regular.svg",
    "chevron_left.svg":  "Chevron%20Left/SVG/ic_fluent_chevron_left_24_regular.svg",
    "chevron_right.svg": "Chevron%20Right/SVG/ic_fluent_chevron_right_24_regular.svg",
    "zoom_out.svg":      "Zoom%20Out/SVG/ic_fluent_zoom_out_24_regular.svg",
    "zoom_in.svg":       "Zoom%20In/SVG/ic_fluent_zoom_in_24_regular.svg",
    "fit_page.svg":      "Fit%20Page/SVG/ic_fluent_fit_page_24_regular.svg",
    "save.svg":          "Save/SVG/ic_fluent_save_24_regular.svg",
    "print.svg":         "Print/SVG/ic_fluent_print_24_regular.svg",
    "usb.svg":           "Usb%20Plug/SVG/ic_fluent_usb_plug_24_regular.svg",
    "pen.svg":           "Pen/SVG/ic_fluent_pen_24_regular.svg",
    "fullscreen.svg":    "Full%20Screen%20Maximize/SVG/ic_fluent_full_screen_maximize_24_regular.svg",
}

BASE = "https://raw.githubusercontent.com/microsoft/fluentui-system-icons/main/assets"

for filename, path in ICONS.items():
    url = f"{BASE}/{path}"
    dest = f"assets/icons/{filename}"
    try:
        urllib.request.urlretrieve(url, dest)
        # Kiểm tra file hợp lệ
        with open(dest, "r") as f:
            content = f.read()
        if "<svg" in content:
            print(f"✅ {filename}")
        else:
            print(f"⚠️  {filename} — tải về nhưng không phải SVG hợp lệ")
    except Exception as e:
        print(f"❌ {filename}: {e}")

for filename, path in FIXES.items():
    url = f"{BASE}/{path}"
    dest = f"assets/icons/{filename}"
    try:
        urllib.request.urlretrieve(url, dest)
        with open(dest, "r") as f:
            content = f.read()
        if "<svg" in content:
            print(f"✅ {filename}")
        else:
            print(f"⚠️ {filename} — không phải SVG hợp lệ")
    except Exception as e:
        print(f"❌ {filename}: {e}")