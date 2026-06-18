#!/bin/bash
# ============================================================
# 3T READER - macOS Professional Build & Package Script
# Tạo bản cài đặt hoàn chỉnh kiểu drag-to-Applications
# ============================================================
set -e

APP_NAME="3T Reader"
APP_BUNDLE="3T Reader.app"
DMG_NAME="3T_Reader_mac_1.0.19"
VERSION="1.0.19"
BUILD_DIR="dist"

echo "╔══════════════════════════════════════════════╗"
echo "║   3T READER MAC BUILD PIPELINE v${VERSION}   ║"
echo "╚══════════════════════════════════════════════╝"

# ── BƯỚC 1: Dọn sạch bản build cũ ─────────────────────────
echo ""
echo "▶ Bước 1/5: Dọn sạch bản build cũ..."
rm -rf build dist
echo "  ✓ Sạch sẽ!"

# ── BƯỚC 2: Build .app bundle với PyInstaller ──────────────
echo ""
echo "▶ Bước 2/5: Build app bundle (PyInstaller)..."
echo "  Đây có thể mất 5-10 phút, vui lòng đợi..."
pyinstaller --clean 3T_Reader.spec
echo "  ✓ Build xong!"

# ── Kiểm tra app bundle ────────────────────────────────────
APP_PATH="${BUILD_DIR}/${APP_BUNDLE}"
if [ ! -d "${APP_PATH}" ]; then
    echo "  ✗ LỖI: Không tìm thấy ${APP_PATH}! Build thất bại."
    exit 1
fi
echo "  ✓ App bundle tại: ${APP_PATH}"

# ── BƯỚC 3: Xoá quarantine attribute (tránh xác minh chậm) 
echo ""
echo "▶ Bước 3/5: Xoá quarantine attributes..."
xattr -cr "${APP_PATH}" 2>/dev/null || true
echo "  ✓ Xong!"

# ── BƯỚC 4: Tạo DMG chuyên nghiệp kiểu drag-to-Applications 
echo ""
echo "▶ Bước 4/5: Tạo DMG installer (drag-to-Applications)..."

STAGING_DIR="dist/dmg_staging"
DMG_OUTPUT="${BUILD_DIR}/${DMG_NAME}.dmg"
BG_IMAGE="assets/dmg_background.png"

rm -rf "${STAGING_DIR}"
mkdir -p "${STAGING_DIR}"

# Copy app vào staging
cp -R "${APP_PATH}" "${STAGING_DIR}/"

# Tạo symlink Applications
ln -s /Applications "${STAGING_DIR}/Applications"

rm -f "${DMG_OUTPUT}"

# Tạo DMG với create-dmg nếu có (đẹp hơn)
if command -v create-dmg &> /dev/null && [ -f "${BG_IMAGE}" ]; then
    echo "  Dùng create-dmg (professional installer)..."
    create-dmg \
        --volname "${APP_NAME}" \
        --volicon "assets/app.icns" \
        --background "${BG_IMAGE}" \
        --window-pos 200 120 \
        --window-size 660 400 \
        --icon-size 128 \
        --icon "${APP_BUNDLE}" 165 230 \
        --hide-extension "${APP_BUNDLE}" \
        --app-drop-link 495 230 \
        --no-internet-enable \
        "${DMG_OUTPUT}" \
        "${STAGING_DIR}" || {
        echo "  create-dmg thất bại, dùng hdiutil fallback..."
        hdiutil create \
            -volname "${APP_NAME}" \
            -srcfolder "${STAGING_DIR}" \
            -ov \
            -format UDZO \
            "${DMG_OUTPUT}"
    }
else
    echo "  Dùng hdiutil..."
    hdiutil create \
        -volname "${APP_NAME}" \
        -srcfolder "${STAGING_DIR}" \
        -ov \
        -format UDZO \
        "${DMG_OUTPUT}"
fi

rm -rf "${STAGING_DIR}"

if [ ! -f "${DMG_OUTPUT}" ]; then
    echo "  ✗ LỖI: Không tạo được DMG!"
    exit 1
fi

DMG_SIZE=$(du -sh "${DMG_OUTPUT}" | cut -f1)
echo "  ✓ DMG tạo xong! Kích thước: ${DMG_SIZE}"
echo "  ✓ Đường dẫn: ${DMG_OUTPUT}"

# ── BƯỚC 5: Upload lên VPS ─────────────────────────────────
echo ""
echo "▶ Bước 5/5: Upload lên VPS (3tcomputer.com)..."

VPS_HOST="hieupt"
VPS_PATH="/home/hieupt/3t_backend/static"
REMOTE_FILE="${VPS_PATH}/${DMG_NAME}.dmg"

# Upload file
scp -o StrictHostKeyChecking=no "${DMG_OUTPUT}" "${VPS_HOST}:${REMOTE_FILE}"
echo "  ✓ Upload xong! File tại: ${REMOTE_FILE}"

# Cập nhật download_url trên server
ssh -o StrictHostKeyChecking=no "${VPS_HOST}" "
    sed -i 's|\"download_url\": \"https://ssh.3tcomputer.com/static/.*\.dmg\"|\"download_url\": \"https://ssh.3tcomputer.com/static/${DMG_NAME}.dmg\"|g' /home/hieupt/3t_backend/vps_server.py
    echo 'URL updated in vps_server.py'
    # Reload server
    pkill -f 'python.*vps_server' || true
    sleep 1
    cd /home/hieupt/3t_backend && nohup python3 vps_server.py > /tmp/vps_server.log 2>&1 &
    sleep 2
    echo 'Server reloaded!'
"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║           BUILD HOÀN TẤT THÀNH CÔNG!        ║"
echo "╠══════════════════════════════════════════════╣"
echo "║  Phiên bản : v${VERSION}                     ║"
echo "║  DMG       : ${DMG_OUTPUT}"
echo "║  URL       : https://ssh.3tcomputer.com/static/${DMG_NAME}.dmg"
echo "╚══════════════════════════════════════════════╝"
