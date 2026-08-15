APP_NAME = "3T Reader"
APP_ID = "com.3t.reader"
APP_DATA_DIR_NAME = "3T Reader"
WINDOW_TITLE = APP_NAME
MUTEX_NAME = "3T_Reader_SingleInstance_v1"

# VPS backend — set VPS_LICENSE_BASE_URL="" to run without license enforcement
VPS_LICENSE_BASE_URL = "https://reader.3tcomputer.com"

# Transfer-gateway V2 — companion device pairing cho key doanh nghiệp 3TR-E.
# Tách biệt hoàn toàn VPS_LICENSE_BASE_URL (V1), theo SPEC_TRANSFER_GATEWAY_V2.md.
TRANSFER_GATEWAY_BASE_URL = "https://transfer.3tcomputer.com"

UPDATE_MANIFEST_URL = f"{VPS_LICENSE_BASE_URL}/api/v1/update/check"
UPDATE_CHANNEL = "stable"
LANGUAGE_PACK_BASE_URL = f"{VPS_LICENSE_BASE_URL}/api/v1/language"
OCR_TESSERACT_INSTALLER_URL = f"{VPS_LICENSE_BASE_URL}/downloads/ocr/tesseract-ocr-windows-x64.exe"
OCR_TESSDATA_BASE_URL = f"{VPS_LICENSE_BASE_URL}/downloads/ocr/tessdata"
# Auto-OCR is isolated in a helper process so native OCR/PDF failures cannot
# terminate the Qt viewer. The helper creates no console window on Windows.
AUTO_OCR_ON_OPEN = True
