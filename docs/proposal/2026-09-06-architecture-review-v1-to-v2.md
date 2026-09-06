# Biên bản rà soát kiến trúc — Phiên bản 1.0 sang Phiên bản 2.0

**Tài liệu được rà soát:** Đề xuất kiến trúc hệ thống AI Engineering Assistant, phiên bản 1.0

| | |
|---|---|
| **Loại tài liệu** | Biên bản rà soát kiến trúc (Architecture Review Memo) |
| **Ngày rà soát** | 06/09/2026 |
| **Người rà soát** | Kiến trúc sư trưởng giải pháp (Principal Enterprise Architect) |
| **Đối tượng đọc** | CTO, Giám đốc Kỹ thuật, Trưởng bộ phận Thiết kế |
| **Mục đích** | Xác định khoảng trống của bản 1.0 và phạm vi hiệu chỉnh cho bản 2.0 |
| **Kết luận chung** | Kiến trúc kỹ thuật đạt yêu cầu; cần bổ sung phần vận hành, quản trị và luận chứng đầu tư |

---

## 1. Tóm tắt kết quả rà soát

Bản 1.0 là một tài liệu kiến trúc kỹ thuật đạt chất lượng: các quyết định kiến trúc được nêu rõ kèm phương án đã cân nhắc, ranh giới an toàn giữa thành phần AI và hệ thống nghiệp vụ được thiết kế chặt chẽ, và mô hình dữ liệu tình huống kỹ thuật đã được đặc tả ở mức có thể triển khai.

Tuy nhiên, bản 1.0 **chưa phải là một hồ sơ đề xuất đầu tư**. Tài liệu trả lời tốt câu hỏi "hệ thống hoạt động như thế nào" nhưng chưa trả lời đủ ba câu hỏi mà lãnh đạo bắt buộc phải có câu trả lời trước khi phê duyệt vốn: **đơn vị vận hành hệ thống này ra sao, hệ thống cải thiện theo thời gian bằng cơ chế nào, và đo hiệu quả đầu tư bằng chỉ tiêu gì.**

Khoảng trống này không phải lỗi diễn đạt. Nó là khoảng trống về phạm vi: bản 1.0 được viết từ góc nhìn kiến trúc hệ thống, trong khi hồ sơ trình phê duyệt cần thêm góc nhìn vận hành và góc nhìn tài chính.

**Kết luận:** giữ nguyên toàn bộ nội dung kỹ thuật, bổ sung bảy nhóm nội dung mới, và tái cấu trúc tài liệu thành sáu phần theo trình tự ra quyết định của lãnh đạo.

---

## 2. Điểm mạnh cần được giữ nguyên

Các nội dung dưới đây đã đạt yêu cầu và **không được sửa đổi** trong bản 2.0, trừ việc cập nhật số hiệu tham chiếu chéo.

| # | Điểm mạnh | Vị trí trong bản 1.0 |
|---|---|---|
| M-01 | Quyết định kiến trúc được trình bày dạng ADR có phương án cân nhắc và lý do lựa chọn, cho phép lãnh đạo phản biện từng quyết định thay vì chấp nhận cả gói | Mục 0.4 |
| M-02 | Ranh giới an toàn "AI không truy cập trực tiếp dữ liệu" được thiết kế nhất quán và áp dụng xuyên suốt, kể cả cho MCP | AD-02, Mục 5.4, Mục 12 |
| M-03 | Mô hình dữ liệu tình huống kỹ thuật được đặc tả đầy đủ ở mức trường dữ liệu, kèm lý do cho từng nhóm trường | Mục 7.4, 7.5 |
| M-04 | Nguyên tắc phê duyệt của con người được đặt ở mức quyết định kiến trúc, không phải mức tính năng | AD-04 |
| M-05 | Nguyên tắc ưu tiên độ tin cậy hơn độ bao phủ, kèm ba mức phản hồi khi hệ thống không đủ căn cứ | AD-08, Mục 5.7 |
| M-06 | Giả định được liệt kê kèm phân tích hệ quả nếu giả định sai — đặc biệt GĐ-06 về khả năng thu thập dữ liệu tình huống | Mục 0.3 |
| M-07 | Lộ trình theo giai đoạn có giá trị độc lập, có tiêu chí kết thúc và điều kiện dừng | AD-06, Mục 13 |
| M-08 | Từ chối đưa ra con số lợi ích chưa đo được, kèm cam kết đo số liệu nền trong giai đoạn 1 | Mục 1.3, 13.2 |
| M-09 | Phân định trách nhiệm rõ giữa công việc phần mềm và công việc nghiệp vụ (rà soát tài liệu, xác nhận công thức tính toán) | Mục 14.2 |

Điểm M-08 cần được nhấn mạnh: việc bản 1.0 **không** đưa ra tuyên bố kiểu "giảm 40% thời gian" khi chưa có số liệu nền là một lựa chọn đúng và phải được giữ trong bản 2.0. Phần bổ sung về chi phí và hiệu quả đầu tư ở bản 2.0 vì vậy trình bày **cấu trúc chi phí và phương pháp đo**, không trình bày con số tuyệt đối chưa có căn cứ.

---

## 3. Khoảng trống đã xác định

### 3.1 Khoảng trống về kiến trúc

| Mã | Khoảng trống | Hệ quả nếu không xử lý |
|---|---|---|
| KT-01 | Tool Calling được trình bày lồng trong mục AI Agent, chưa có đặc tả hợp đồng công cụ (tool contract): lược đồ tham số, tính bất biến của kết quả, quản lý phiên bản, xử lý lỗi và timeout | Đội phát triển không có chuẩn chung khi bổ sung công cụ mới; mỗi công cụ được viết theo một quy ước riêng |
| KT-02 | Chưa có kiến trúc triển khai production: phân vùng mạng, mô hình môi trường, cơ chế phát hành, giám sát, khôi phục sự cố | Không đủ cơ sở để lập dự toán hạ tầng và không đủ cơ sở để bộ phận vận hành đánh giá khả năng tiếp nhận |
| KT-03 | Kiến trúc RAG chưa nêu chiến lược cắt đoạn theo từng loại tài liệu, cơ chế xếp hạng lại (reranking), và cách xử lý bảng biểu kỹ thuật | Chất lượng truy xuất phụ thuộc vào lựa chọn ngẫu hứng của người triển khai |
| KT-04 | Chưa mô tả kiến trúc chỉ thị hệ thống (prompt architecture) và cơ chế kiểm soát phiên bản của chỉ thị | Thay đổi chỉ thị làm thay đổi hành vi hệ thống mà không có dấu vết kiểm soát |
| KT-05 | Vòng lặp Agent chưa nêu mô hình trạng thái và điều kiện dừng ở mức đủ chi tiết để hiện thực | Rủi ro vòng lặp không hội tụ, chi phí xử lý không kiểm soát được |
| KT-06 | Chưa có kiến trúc nền tảng tri thức thống nhất: tài liệu, tình huống, kết quả tính toán và quyết định kỹ thuật được mô tả rời rạc ở các mục khác nhau | Lãnh đạo khó nhận ra rằng bốn nhóm dữ liệu này hợp thành **một** tài sản duy nhất của đơn vị |

### 3.2 Khoảng trống về nghiệp vụ và đầu tư

| Mã | Khoảng trống | Hệ quả nếu không xử lý |
|---|---|---|
| NV-01 | Chưa có luận chứng đầu tư: cây giá trị, cơ chế tác động tới năng suất, phương pháp quy đổi lợi ích | Lãnh đạo không có cơ sở so sánh khoản đầu tư này với các đề xuất đầu tư khác |
| NV-02 | Chưa có mô hình chi phí: các thành phần chi phí, yếu tố dẫn dắt chi phí, chiến lược tối ưu | Không phê duyệt được ngân sách; rủi ro chi phí vận hành vượt dự kiến sau khi mở rộng người dùng |
| NV-03 | Giá trị bảo toàn tri thức được nêu định tính, chưa gắn với cơ chế đo lường | Không chứng minh được tài sản tri thức đang hình thành hay không |
| NV-04 | Chưa nêu rõ chi phí cơ hội của phương án không làm gì, và chi phí của phương án thay thế (mua công cụ thương mại) | Thiếu một nhánh so sánh mà lãnh đạo chắc chắn sẽ hỏi |

### 3.3 Khoảng trống về vận hành và quản trị

| Mã | Khoảng trống | Hệ quả nếu không xử lý |
|---|---|---|
| VH-01 | Chưa có mô hình vận hành: ai sở hữu hệ thống về mặt nghiệp vụ, ai chịu trách nhiệm chất lượng tri thức, ai quyết định bổ sung công cụ mới | Hệ thống không có chủ sở hữu thực chất; chất lượng suy giảm sau khi dự án kết thúc |
| VH-02 | Chưa có quy trình quản trị tri thức: tài liệu vào hệ thống theo đường nào, ai duyệt, rà soát định kỳ ra sao | Kho tri thức nhiễm dữ liệu lỗi thời theo thời gian |
| VH-03 | Quy trình phê duyệt kỹ thuật được nêu ở mức nguyên tắc, chưa mô tả thành luồng công việc có trạng thái và vai trò | Không tích hợp được vào quy trình kiểm soát chất lượng hiện hành của đơn vị |
| VH-04 | Chưa có cơ chế quản trị AI: hội đồng nào phê duyệt việc mở rộng phạm vi công cụ, tần suất rà soát, tiêu chí dừng | Phạm vi hành động của hệ thống mở rộng dần mà không qua kiểm soát |
| VH-05 | Chưa mô tả vòng đời tri thức khép kín từ tương tác của kỹ sư đến tình huống được tái sử dụng | Cơ chế "hệ thống càng dùng càng giàu tri thức" chỉ được khẳng định, chưa được thiết kế |
| VH-06 | Chưa có khung đánh giá hiệu quả: chỉ tiêu kỹ thuật, chỉ tiêu nghiệp vụ, phương pháp đo, tần suất, ngưỡng chuyển giai đoạn | Không xác định được hệ thống thành công hay thất bại; tiêu chí kết thúc giai đoạn trong lộ trình không có công cụ đo tương ứng |

### 3.4 Khoảng trống về định hướng mở rộng

| Mã | Khoảng trống | Hệ quả nếu không xử lý |
|---|---|---|
| MR-01 | Kiến trúc đa tác tử được nêu một dòng, chưa mô tả mô hình phối hợp và ranh giới trách nhiệm giữa các tác tử | Phần định hướng đọc như một danh sách nguyện vọng, không như một kế hoạch kiến trúc |
| MR-02 | Chưa nêu rõ nguyên tắc phê duyệt của con người được duy trì ra sao trong mô hình nhiều tác tử | Rủi ro người đọc hiểu rằng ràng buộc cốt lõi của tài liệu sẽ được nới lỏng ở giai đoạn sau |

---

## 4. Danh mục hiệu chỉnh cho bản 2.0

Mỗi dòng dưới đây ánh xạ một khoảng trống sang mục cụ thể trong bản 2.0 khắc phục khoảng trống đó.

| # | Nội dung hiệu chỉnh | Khoảng trống xử lý | Mục trong bản 2.0 | Loại |
|---|---|---|---|---|
| 1 | Bổ sung mục luận chứng đầu tư: cây giá trị, cơ chế tác động năng suất, phương pháp quy đổi, so sánh phương án | NV-01, NV-03, NV-04 | Mục 3 | Mới |
| 2 | Bổ sung mục nền tảng tri thức kỹ thuật, hợp nhất bốn nhóm tài sản dữ liệu thành một kiến trúc | KT-06 | Mục 5 | Mới |
| 3 | Tách Tool Calling thành mục riêng, bổ sung đặc tả hợp đồng công cụ, quản lý phiên bản, xử lý lỗi | KT-01 | Mục 8 | Mới |
| 4 | Bổ sung kiến trúc chỉ thị hệ thống và mô hình trạng thái của Agent | KT-04, KT-05 | Mục 7.4, 7.6 | Bổ sung |
| 5 | Bổ sung chiến lược cắt đoạn theo loại tài liệu, cơ chế xếp hạng lại, xử lý bảng biểu | KT-03 | Mục 9.3, 9.5 | Bổ sung |
| 6 | Bổ sung mục mô hình vận hành AI: sở hữu, vai trò, quy trình quản trị tri thức, luồng phê duyệt, hội đồng quản trị AI | VH-01, VH-02, VH-03, VH-04 | Mục 14 | Mới |
| 7 | Bổ sung mục quản trị vòng đời tri thức, mô tả vòng khép kín và cơ chế chống suy giảm chất lượng | VH-05 | Mục 15 | Mới |
| 8 | Bổ sung mục khung đánh giá hiệu quả AI: chỉ tiêu kỹ thuật, chỉ tiêu nghiệp vụ, phương pháp đo, ngưỡng chuyển giai đoạn | VH-06 | Mục 16 | Mới |
| 9 | Bổ sung mục kiến trúc triển khai production trên AWS: phân vùng, môi trường, phát hành, giám sát, khôi phục | KT-02 | Mục 19 | Mới |
| 10 | Bổ sung mục mô hình chi phí và chiến lược tối ưu chi phí | NV-02 | Mục 20 | Mới |
| 11 | Mở rộng định hướng đa tác tử thành kiến trúc có mô hình phối hợp và ranh giới trách nhiệm | MR-01, MR-02 | Mục 23 | Mở rộng |
| 12 | Tái cấu trúc tài liệu thành sáu phần theo trình tự ra quyết định; cập nhật toàn bộ tham chiếu chéo | — | Toàn tài liệu | Cấu trúc |
| 13 | Bổ sung sáu quyết định kiến trúc mới (AD-09 đến AD-14) cho các nội dung mới | — | Mục 0.4 | Bổ sung |
| 14 | Đồng bộ ngưỡng đánh giá giữa khung đánh giá và tiêu chí kết thúc giai đoạn trong lộ trình | VH-06 | Mục 16.5, 21 | Nhất quán |
| 15 | Đồng bộ danh mục vai trò giữa ma trận phân quyền bảo mật và mô hình vận hành | VH-01 | Mục 14.2, 17.4 | Nhất quán |

---

## 5. Ánh xạ số hiệu mục giữa hai phiên bản

Bản 2.0 được tái cấu trúc, do đó số hiệu mục thay đổi. Bảng dưới đây phục vụ người đọc đã quen bản 1.0.

| Bản 1.0 | Bản 2.0 | Ghi chú |
|---|---|---|
| 0. Giả định và quyết định kiến trúc | 0 | Bổ sung AD-09 đến AD-14 |
| 1. Tóm tắt dành cho lãnh đạo | 1 | Bổ sung tóm tắt đầu tư |
| 2. Hiện trạng, vấn đề và cơ hội | 2 | Giữ nguyên |
| — | **3. Luận chứng đầu tư và giá trị kỳ vọng** | Mục mới |
| 3. Tổng quan giải pháp | 4 | Giữ nguyên |
| — | **5. Nền tảng tri thức kỹ thuật** | Mục mới |
| 4. Kiến trúc hệ thống tổng thể | 6 | Cập nhật sơ đồ |
| 5. Kiến trúc AI Agent | 7 | Bổ sung 7.4, 7.6 |
| 5.4–5.5 Tool Calling | **8. Kiến trúc Tool Calling** | Tách thành mục riêng, mở rộng |
| 6. Kiến trúc RAG | 9 | Bổ sung 9.3, 9.5 |
| 7. Tri thức tình huống kỹ thuật | 10 | Giữ nguyên |
| 11. Kiến trúc MCP | 11 | Giữ nguyên |
| 8. Kiến trúc dữ liệu và nhật ký | 12 | Giữ nguyên |
| 9. Kiến trúc giao diện | 13 | Giữ nguyên |
| — | **14. Mô hình vận hành AI** | Mục mới |
| — | **15. Quản trị vòng đời tri thức** | Mục mới |
| — | **16. Khung đánh giá hiệu quả AI** | Mục mới |
| 12. Kiến trúc bảo mật | 17 | Giữ nguyên |
| 10. Technology stack | 18 | Giữ nguyên |
| — | **19. Kiến trúc triển khai production** | Mục mới |
| — | **20. Mô hình chi phí** | Mục mới |
| 13. Lộ trình triển khai | 21 | Đồng bộ ngưỡng với Mục 16 |
| 14. Rủi ro và kiểm soát | 22 | Bổ sung rủi ro vận hành |
| 15. Định hướng phát triển | 23 | Mở rộng phần đa tác tử |
| 16. Phụ lục | 24 | Cập nhật danh mục |

---

## 6. Năm câu hỏi và vị trí trả lời trong bản 2.0

Yêu cầu đặt ra là mỗi câu hỏi phải trả lời được bằng cách mở **một** mục, không phải bằng cách ghép nội dung từ nhiều mục.

| Câu hỏi của lãnh đạo | Mục trả lời chính | Mục bổ trợ |
|---|---|---|
| Vì sao đơn vị cần xây dựng hệ thống này? | Mục 3 — Luận chứng đầu tư | Mục 1, Mục 2 |
| Hệ thống hoạt động về mặt kỹ thuật ra sao? | Mục 6 — Kiến trúc tổng thể | Mục 7 đến Mục 13 |
| Đơn vị vận hành hệ thống này như thế nào? | Mục 14 — Mô hình vận hành AI | Mục 17 |
| Hệ thống cải thiện theo thời gian bằng cơ chế nào? | Mục 15 — Quản trị vòng đời tri thức | Mục 10 |
| Đo hiệu quả bằng chỉ tiêu gì? | Mục 16 — Khung đánh giá hiệu quả AI | Mục 21 |

---

## 7. Nguyên tắc giữ nguyên khi hiệu chỉnh

Ba nguyên tắc dưới đây ràng buộc toàn bộ nội dung bổ sung của bản 2.0:

1. **Không tăng mức cam kết về lợi ích khi chưa có số liệu.** Phần luận chứng đầu tư trình bày cơ chế tạo giá trị và phương pháp đo, không trình bày tỉ lệ cải thiện tuyệt đối. Phần chi phí trình bày cấu trúc chi phí và yếu tố dẫn dắt, kèm ghi chú rằng đơn giá cần báo giá tại thời điểm triển khai.
2. **Không nới lỏng nguyên tắc phê duyệt của con người.** Nguyên tắc AD-04 được duy trì trong toàn bộ mục mới, bao gồm cả mục định hướng đa tác tử.
3. **Không giảm độ sâu kỹ thuật.** Nội dung kỹ thuật của bản 1.0 được giữ toàn bộ; các mục mới bổ sung thêm chiều vận hành và chiều tài chính, không thay thế chiều kỹ thuật.

---

*Kết thúc biên bản rà soát. Tài liệu bản 2.0: `2026-09-06-ai-engineering-assistant-architecture-vi-v2.md`.*
