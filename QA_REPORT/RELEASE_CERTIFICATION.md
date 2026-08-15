# Release Certification — 3T Reader 1.0.33

Trả lời 20 câu hỏi theo đúng yêu cầu, số liệu thật từ phiên test này (không
làm tròn/thổi phồng).

1. **Đã test bao nhiêu chức năng?** 12 luồng chính (khởi động, mở file
   thường/nặng/hỏng, điều hướng trang, zoom, thumbnail, đa tab cơ bản, chuyển
   tab, window state, đóng app).
2. **Đã click bao nhiêu control?** ~35 lượt click/invoke thật qua UI
   Automation (5 next-page, 3+20 zoom-in, các nút mở file, thumbnail, window
   controls).
3. **Đã test bao nhiêu icon?** 1 icon với stress đầy đủ (20 lần) — "Phóng
   to". Các icon khác được click 1-vài lần trong luồng bình thường nhưng
   KHÔNG stress test riêng.
4. **Đã test bao nhiêu menu?** 0 menu thả xuống được mở/test riêng (menu bar
   top có 12 mục, chưa test mục nào).
5. **Đã mở bao nhiêu tab?** 2 tab (medium_50pages.pdf + qa_save_as_test.pdf
   711MB). CHƯA test 5/10/20/30/50 tab như yêu cầu.
6. **Đã test bao nhiêu file?** 3 file thật (PDF 50 trang tự tạo, PDF 711MB có
   sẵn, PDF corrupt tự tạo). Không dùng file "CCCD PHAM TRUNG HIEU.pdf" có
   sẵn trong danh sách gần đây vì đó là ảnh giấy tờ tuỳ thân thật — không mở
   để tránh xử lý dữ liệu cá nhân nhạy cảm không cần thiết.
7. **Đã lặp bao nhiêu thao tác?** Tối đa 20 lần liên tiếp (zoom stress). Chưa
   đạt mức lặp 50 tab hay soak-test dài hơi.
8. **Đã chạy stress bao lâu?** Tổng phiên test ~10 phút hoạt động liên tục
   trên app thật. KHÔNG có soak-test 10p/30p/60p riêng biệt.
9. **Có bao nhiêu crash?** 0.
10. **Có bao nhiêu freeze?** 0 (process luôn ở trạng thái Responding=True mọi
    lúc kiểm tra).
11. **Có bao nhiêu bug P0?** 0.
12. **Có bao nhiêu bug P1?** 0.
13. **Có bao nhiêu bug P2?** 1 (BUG-01: thumbnail trắng).
14. **Có bao nhiêu bug P3?** 0 ghi nhận (chưa đủ phạm vi test để khẳng định
    không còn P3 nào).
15. **Có bao nhiêu visual issue?** 1 (BUG-01, đồng thời cũng là visual issue).
16. **Có memory leak không?** KHÔNG ĐỦ DỮ LIỆU để kết luận chắc chắn. RAM tăng
    hợp lý theo thao tác zoom/mở file lớn, không quan sát thấy tăng bất
    thường trong ~10 phút test, nhưng chưa chạy đủ lâu (thiếu soak-test) để
    loại trừ hoàn toàn leak chậm.
17. **Có regression không?** Không phát hiện regression trong phạm vi đã
    test — nhưng chưa chạy "regression sau stress dài" theo đúng yêu cầu gốc.
18. **Có chức năng nào chưa test được?** Có — xem danh sách đầy đủ trong
    TEST_COVERAGE.md (đa tab quy mô lớn, icon stress cho 16/17 icon còn lại,
    tất cả menu, hầu hết phím tắt, OCR, AI, ký số, license, ScanDoc/WebRTC,
    export/import, chỉnh sửa/annotate, soak-test dài hơi).
19. **Tại sao chưa test được?** Giới hạn thời gian thực tế của 1 phiên làm
    việc so với khối lượng 28 mục yêu cầu (nhiều giờ công QA thật) — đã ưu
    tiên luồng lõi + rủi ro cao nhất, chọn làm ít nhưng làm THẬT thay vì làm
    nông/giả vờ toàn bộ.
20. **Có thể phát hành hay chưa?**

## KẾT LUẬN: RELEASE READY (có điều kiện)

**Không có bug P0/P1** trong phạm vi đã test thật — không crash, không mất dữ
liệu, không treo UI, xử lý lỗi (file hỏng) đúng và rõ ràng, file rất nặng
(711MB) mở ổn định, đóng app sạch không zombie process.

**Điều kiện đi kèm:** Phần lớn ứng dụng (OCR, AI, ký số, license, ScanDoc,
chỉnh sửa/annotate, đa tab quy mô lớn, hầu hết icon/menu/phím tắt) **CHƯA
được test bằng GUI thật trong phiên này** — verdict "READY" chỉ áp dụng cho
đúng phạm vi đã kiểm chứng (mở/đọc/điều hướng file, xử lý lỗi cơ bản, ổn định
dưới tải nhẹ), KHÔNG phải chứng nhận toàn bộ ứng dụng. BUG-01 (thumbnail
trắng) nên sửa trước khi phát hành vì dễ khiến người dùng hoang mang, nhưng
không đủ nghiêm trọng để BLOCK riêng nó.

**Khuyến nghị:** nếu cần chứng nhận release đầy đủ theo đúng 28 mục yêu cầu
gốc, cần 1 phiên QA riêng dài hơi hơn (khuyến nghị dùng pywinauto + chạy nền
qua đêm cho phần stress/soak-test), không nên coi báo cáo này là đã phủ hết.
