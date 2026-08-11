# 14 — Project Health Score

Thang điểm 0-100 mỗi hạng mục. Định tính có căn cứ (dựa trên bằng chứng cụ thể trong 13 báo cáo trước), không phải công thức toán học chính xác — nêu rõ lý do cho mỗi điểm để có thể tranh luận/điều chỉnh.

| Hạng mục | Điểm | Lý do |
|---|---|---|
| **Architecture** | 62 | God-object `window.py`, trùng logic annotate/pages — nhưng có abstraction PDF engine tốt, pattern threading nền có document rõ ràng. |
| **Maintainability** | 63 | Duplication có thật (QSS, DownloadThread), coupling UI/logic chặt — nhưng naming nhất quán, module hóa theo tính năng hợp lý ở tầng `app/actions/`. |
| **Scalability** | 65 | App desktop single-user, không có concern scale kiểu web service; đánh giá theo nghĩa "codebase phình to có kiểm soát không" — god-object đang phát triển theo hướng khó kiểm soát nếu không can thiệp. |
| **Readability** | 72 | Quy ước đặt tên nhất quán, không magic-number rải rác; điểm trừ vì vài file quá dài (3000+ dòng) khó đọc trọn vẹn. |
| **Performance** | 82 | Đã cải thiện đáng kể trong chính phiên này (3 vấn đề chặn UI thread nghiêm trọng đã sửa). Còn 1 vòng lặp thiếu timeout (Medium). |
| **Security** | 70 | Nền tảng bảo mật tốt (license verify, local server, subprocess handling đều đúng chuẩn qua audit kỹ) — nhưng bị kéo điểm mạnh vì 1 vấn đề pháp lý Critical thật (PyMuPDF/AGPL) đang tồn tại trong bản build production. |
| **UI/UX** | 70 | Trải nghiệm cốt lõi ổn (ribbon, sidebar, TOC), nhưng có 1 bug hiển thị thật (3 dialog sai theme) và vài dialog kích thước cố định rủi ro cắt nội dung. |
| **Accessibility** | 25 | 0 sử dụng Qt Accessibility API, không mnemonic bàn phím cho menu — điểm thấp phản ánh đúng thực trạng, không phải ưu tiên khẩn cấp cho thị trường hiện tại của sản phẩm. |
| **Testing** | 58 | 325 test case, nhưng phần lớn kiểm tra chuỗi văn bản trong source thay vì gọi hàm thật + assert kết quả — hạn chế thực sự trong khả năng bắt regression, dù đây là hệ quả hợp lý của coupling UI/logic, không phải do viết test ẩu. |
| **Code Quality** | 68 | Error-handling phần lớn hợp lý (đã kiểm tra mẫu kỹ), 1 trường hợp nguy hiểm đã sửa; duplication có thật nhưng không lan rộng. |

## Overall Health: **65/100**

**Diễn giải**: sản phẩm hoạt động ổn định cho quy mô 1 người/nhóm nhỏ phát triển, phục vụ thị trường ngách (Vietnamese PDF reader thương mại). Điểm không cao chủ yếu do 2 nguyên nhân có trọng số khác nhau:
1. **Accessibility gần như bằng 0** — kéo điểm mạnh nhưng không phản ánh mức độ khẩn cấp thực sự cho sản phẩm hiện tại.
2. **1 rủi ro pháp lý Critical thật** (PyMuPDF/AGPL) — kéo điểm Security dù nền tảng bảo mật kỹ thuật thực chất tốt.

Nếu loại trừ 2 yếu tố này (accessibility chưa phải ưu tiên thị trường, AGPL là quyết định business chờ xử lý chứ không phải lỗ hổng kỹ thuật), điểm sức khỏe kỹ thuật thuần túy của phần còn lại ở mức **~70-75/100** — phản ánh đúng hơn 1 app đã được đầu tư sửa lỗi nghiêm túc (11 fix production trong chính phiên audit này) nhưng vẫn còn nợ kỹ thuật tích lũy tự nhiên của 1 dự án đang phát triển nhanh.

## So sánh trước/sau phiên làm việc này (ước lượng định tính)

| Hạng mục | Trước phiên (ước lượng) | Sau phiên (hiện tại) |
|---|---|---|
| Performance | ~55 (3 vấn đề chặn UI thread nghiêm trọng) | 82 |
| Security | ~65 (2 Medium chưa sửa + chưa phát hiện AGPL) | 70 |
| Bug/Crash risk | Cao (crash native đã xác nhận qua log thật) | Thấp hơn đáng kể (nguyên nhân chính đã chặn) |
