APP_NAME = "3T Reader"
APP_ID = "com.3t.reader"
APP_DATA_DIR_NAME = "3T Reader"
WINDOW_TITLE = APP_NAME
MUTEX_NAME = "3T_Reader_SingleInstance_v1"

# VPS backend — set VPS_LICENSE_BASE_URL="" to run without license enforcement
VPS_LICENSE_BASE_URL = "http://192.168.1.254:8000"

UPDATE_MANIFEST_URL = f"{VPS_LICENSE_BASE_URL}/api/v1/update/check"
UPDATE_CHANNEL = "stable"
