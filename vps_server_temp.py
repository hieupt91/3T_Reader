import os
import requests
from flask import Flask, request, jsonify, Response

app = Flask(__name__)

# ---------------------------------------------------------
# 1. API TRẢ VỀ THÔNG TIN CẬP NHẬT TỰ ĐỘNG (AUTO-UPDATE)
# ---------------------------------------------------------
@app.route('/api/v1/update/check', methods=['GET'])
def check_update():
    client_version = request.args.get('version', '')
    platform = request.args.get('platform', 'win').lower()
    
    if platform in ['mac', 'darwin']:
        # --- CẤU HÌNH DÀNH CHO MAC ---
        LATEST_VERSION = '1.0.19'
        
        if client_version != LATEST_VERSION:
            return jsonify({
                "update_available": True,
                "version": LATEST_VERSION,
                "release_notes": "Bản cập nhật tính năng Đọc Sách Mac OS:\n- Tích hợp tính năng Đọc Offline cực mượt (Piper TTS)\n- Tự động nhận diện ngôn ngữ Anh/Việt.\n- Thêm thanh trượt chỉnh tốc độ đọc.",
                "download_url": "https://ssh.3tcomputer.com/static/3T_Reader_mac_1.0.8.dmg",
                "mandatory": False
            })
        else:
            return jsonify({"update_available": False})
            
    else:
        # --- CẤU HÌNH DÀNH CHO WINDOWS ---
        LATEST_VERSION = '1.0.18'
        
        if client_version != LATEST_VERSION:
            return jsonify({
                "update_available": True,
                "version": LATEST_VERSION,
                "release_notes": "Bản cập nhật quan trọng Phase 2:\n- Sửa lỗi xuất Word/Excel cực mượt (dùng Subprocess)\n- Đóng gói đầy đủ thư viện AI\n- Tích hợp Ký nhiều cấu hình & LTV\n- Giải nén bản cài đặt siêu tốc",
                "download_url": "https://reader.3tcomputer.com/downloads/Setup_3T_Reader_v1.0.18.exe",
                "mandatory": False
            })
        else:
            return jsonify({"update_available": False})

# ---------------------------------------------------------
# 2. API MÁY CHỦ DẤU THỜI GIAN (TSA - Time Stamping Authority)
# ---------------------------------------------------------
@app.route('/api/v1/tsa', methods=['POST'])
def proxy_tsa():
    try:
        # Lấy dữ liệu nhị phân (ASN.1 TimeStampReq) từ 3T Reader
        tsa_req_data = request.get_data()
        
        # Chuyển tiếp tới máy chủ Timestamp quốc tế (Ví dụ DigiCert)
        TSA_URL = "http://timestamp.digicert.com"
        
        headers = {'Content-Type': 'application/timestamp-query'}
        response = requests.post(TSA_URL, data=tsa_req_data, headers=headers)
        
        # Trả lại ASN.1 TimeStampResp cho 3T Reader
        return Response(
            response.content, 
            status=response.status_code, 
            mimetype='application/timestamp-reply'
        )
    except Exception as e:
        print(f"TSA Error: {e}")
        return Response("TSA Proxy Error", status=500)

if __name__ == '__main__':
    # Chạy trên port 80 hoặc 5000 tuỳ cấu hình Reverse Proxy (Nginx) của VPS
    app.run(host='0.0.0.0', port=5000)
