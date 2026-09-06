# Đề xuất kiến trúc hệ thống AI Engineering Assistant

**Sử dụng Large Language Model, RAG, Tool Calling và MCP**

| | |
|---|---|
| **Loại tài liệu** | Đề xuất kiến trúc giải pháp (Solution Architecture Proposal) |
| **Phiên bản** | 1.0 |
| **Ngày phát hành** | 06/09/2026 |
| **Người soạn** | Bộ phận Kiến trúc giải pháp |
| **Đối tượng đọc** | Ban Giám đốc, CTO, Trưởng phòng Kỹ thuật, Trưởng bộ phận Thiết kế |
| **Mức độ mật** | Nội bộ — Hạn chế |
| **Trạng thái** | Trình phê duyệt chủ trương |

---

## Mục lục

- [0. Giả định, phạm vi và quyết định kiến trúc](#0-giả-định-phạm-vi-và-quyết-định-kiến-trúc)
- [1. Tóm tắt dành cho lãnh đạo](#1-tóm-tắt-dành-cho-lãnh-đạo)
- [2. Hiện trạng, vấn đề và cơ hội](#2-hiện-trạng-vấn-đề-và-cơ-hội)
- [3. Tổng quan giải pháp đề xuất](#3-tổng-quan-giải-pháp-đề-xuất)
- [4. Kiến trúc hệ thống tổng thể](#4-kiến-trúc-hệ-thống-tổng-thể)
- [5. Kiến trúc AI Agent](#5-kiến-trúc-ai-agent)
- [6. Kiến trúc RAG](#6-kiến-trúc-rag)
- [7. Hệ thống tri thức tình huống kỹ thuật](#7-hệ-thống-tri-thức-tình-huống-kỹ-thuật)
- [8. Kiến trúc dữ liệu và nhật ký](#8-kiến-trúc-dữ-liệu-và-nhật-ký)
- [9. Kiến trúc giao diện người dùng](#9-kiến-trúc-giao-diện-người-dùng)
- [10. Đề xuất technology stack](#10-đề-xuất-technology-stack)
- [11. Kiến trúc MCP](#11-kiến-trúc-mcp)
- [12. Kiến trúc bảo mật](#12-kiến-trúc-bảo-mật)
- [13. Lộ trình triển khai](#13-lộ-trình-triển-khai)
- [14. Rủi ro và biện pháp kiểm soát](#14-rủi-ro-và-biện-pháp-kiểm-soát)
- [15. Tầm nhìn mở rộng](#15-tầm-nhìn-mở-rộng)
- [16. Phụ lục](#16-phụ-lục)

---

## 0. Giả định, phạm vi và quyết định kiến trúc

Phần này được đặt trước nội dung chính theo đúng nguyên tắc của một tài liệu kiến trúc: người
đọc cần biết tài liệu dựa trên những giả định nào trước khi đánh giá các đề xuất bên trong.
Nếu một giả định sai, phần kiến trúc phụ thuộc vào nó phải được xem xét lại — chứ không phải
toàn bộ tài liệu bị bác bỏ.

### 0.1 Phạm vi tài liệu

Tài liệu này đề xuất **kiến trúc giải pháp** cho một hệ thống trợ lý kỹ thuật nội bộ. Nội dung
bao gồm: phân tích hiện trạng, mô hình giải pháp, kiến trúc thành phần, mô hình dữ liệu, lộ
trình triển khai theo giai đoạn, phân tích rủi ro và định hướng mở rộng.

Tài liệu **không** bao gồm: dự toán chi phí chi tiết theo từng hạng mục, hồ sơ mua sắm hạ
tầng, thiết kế chi tiết cấp module, và kế hoạch nhân sự chính thức. Những nội dung đó thuộc
bước tiếp theo, sau khi chủ trương được phê duyệt.

### 0.2 Nguyên tắc dùng thuật ngữ

Tài liệu hướng tới người đọc không chuyên về AI. Vì vậy các thuật ngữ tiếng Anh được giữ
nguyên — do đây là tên gọi chuẩn trong ngành, dịch ra sẽ gây khó tra cứu về sau — nhưng **luôn
kèm một dòng giải thích bằng tiếng Việt ở lần xuất hiện đầu tiên**, và sau đó dùng nhất quán:

| Thuật ngữ giữ nguyên | Giải thích ngắn |
|---|---|
| LLM (Large Language Model) | Mô hình ngôn ngữ lớn — phần mềm đọc hiểu và sinh văn bản tự nhiên |
| RAG (Retrieval Augmented Generation) | Cơ chế bắt AI đọc tài liệu công ty trước khi trả lời |
| Tool Calling | Cơ chế cho phép AI gọi một chức năng phần mềm có sẵn thay vì tự suy đoán kết quả |
| MCP (Model Context Protocol) | Chuẩn giao tiếp để nhiều phần mềm AI khác nhau cùng dùng chung một bộ tool |
| Agent | Thành phần điều phối: nhận yêu cầu, quyết định các bước cần làm, gọi tool, tổng hợp kết quả |
| Embedding | Biểu diễn số học của một đoạn văn bản, dùng để tìm đoạn có nội dung gần nghĩa |
| Vector database | Kho lưu trữ chuyên cho embedding, phục vụ tìm kiếm theo ngữ nghĩa |
| Hallucination | Hiện tượng AI trả lời trôi chảy nhưng nội dung sai hoặc bịa đặt |

Các khái niệm nghiệp vụ dùng tiếng Việt thống nhất: *truy xuất* (retrieval), *dẫn chứng*
(evidence/citation), *kiểm định* (verification), *phê duyệt* (approval), *tình huống kỹ thuật*
(engineering case), *nhật ký* (log).

### 0.3 Giả định chính

| # | Giả định | Ảnh hưởng nếu giả định sai |
|---|---|---|
| GĐ-01 | Công ty hoạt động trong lĩnh vực tư vấn thiết kế kết cấu và xây dựng — công việc chính là thiết kế, tính toán, kiểm định và lập hồ sơ kết cấu bê tông cốt thép và kết cấu thép. | Toàn bộ ví dụ trong tài liệu cần thay bằng ví dụ đúng ngành; phần kiến trúc kỹ thuật giữ nguyên. |
| GĐ-02 | Tài liệu kỹ thuật nội bộ hiện phân tán trên file server, email, ổ đĩa cá nhân và thư mục dự án; định dạng chủ yếu là PDF, DOCX, XLSX và bản vẽ DWG/PDF. | Nếu công ty đã có hệ thống quản lý tài liệu tập trung, giai đoạn 1 rút ngắn đáng kể vì bước thu thập dữ liệu đã hoàn tất. |
| GĐ-03 | Công ty đã có một số công cụ tính toán: bảng tính Excel có công thức, phần mềm phân tích kết cấu thương mại (ETABS, SAP2000, SAFE), và có thể có một vài script riêng. | Nếu chưa có công cụ nào gọi được tự động, giai đoạn 2 phải bao gồm việc xây dựng calculation service từ đầu, kéo dài thêm khoảng 2–3 tháng. |
| GĐ-04 | Công ty chấp nhận dùng dịch vụ mô hình ngôn ngữ trên cloud trong phạm vi một tài khoản AWS do công ty kiểm soát, với cam kết dữ liệu không được dùng để huấn luyện mô hình. | Nếu bắt buộc chạy on-premise, cần thay bằng mô hình mã nguồn mở tự vận hành; chi phí hạ tầng tăng và chất lượng trả lời giảm. |
| GĐ-05 | Hồ sơ dự án đã nghiệm thu có thể dùng làm dữ liệu nội bộ, sau khi rà soát ràng buộc bảo mật với chủ đầu tư. | Nếu phần lớn hồ sơ bị ràng buộc bảo mật, tập dữ liệu ban đầu thu hẹp; cần ưu tiên tiêu chuẩn và quy trình nội bộ trước. |
| GĐ-06 | Kỹ sư sẵn sàng ghi nhận lại quyết định kỹ thuật dưới dạng có cấu trúc, nếu thao tác mất dưới 2 phút và mang lại lợi ích thấy được. | Đây là giả định rủi ro nhất. Nếu sai, tầng tri thức tình huống ở Mục 7 không có dữ liệu và hệ thống chỉ dừng ở mức tra cứu tài liệu. |
| GĐ-07 | Công ty có ít nhất một kỹ sư phần mềm nội bộ hoặc đối tác kỹ thuật đủ năng lực vận hành hệ thống trên AWS. | Nếu không, cần bổ sung chi phí thuê ngoài vận hành dài hạn vào bài toán tài chính. |
| GĐ-08 | Mọi kết quả do AI đề xuất đều phải được kỹ sư có thẩm quyền phê duyệt trước khi đưa vào hồ sơ chính thức. | Đây là ràng buộc pháp lý và trách nhiệm nghề nghiệp, không phải lựa chọn thiết kế. Không được nới lỏng trong bất kỳ giai đoạn nào. |

Tài liệu sẽ chính xác hơn nếu có thêm ba đầu vào: danh mục tài liệu kỹ thuật hiện có, mô tả hệ
thống phần mềm đang vận hành, và sơ đồ quy trình thiết kế thực tế. Khi có các dữ liệu đó, các
Mục 2, 6, 7 và 13 nên được hiệu chỉnh theo số liệu thật của công ty.

### 0.4 Quyết định kiến trúc

Mỗi quyết định được trình bày theo cấu trúc: **quyết định — phương án đã cân nhắc — lý do lựa
chọn**. Đây là những lựa chọn ảnh hưởng dài hạn, khó đảo ngược, cần sự đồng thuận của lãnh đạo
trước khi triển khai.

**AD-01 — Dùng RAG thay vì huấn luyện lại mô hình trên dữ liệu công ty**

*Phương án cân nhắc:* (a) fine-tune một mô hình riêng trên toàn bộ hồ sơ công ty; (b) RAG —
giữ mô hình nguyên trạng, nạp tài liệu liên quan vào ngữ cảnh ở mỗi câu hỏi; (c) kết hợp cả hai.

*Lựa chọn:* phương án (b) cho toàn bộ giai đoạn 1–3.

*Lý do:* Fine-tuning không cho phép trích dẫn nguồn — mô hình "nhớ" nội dung nhưng không chỉ
ra được câu trả lời đến từ trang nào của tài liệu nào. Trong ngành kỹ thuật, một câu trả lời
không có dẫn chứng là câu trả lời không dùng được. RAG còn cho phép cập nhật tức thì: sửa một
tiêu chuẩn thì hệ thống trả lời theo bản mới ngay, không cần huấn luyện lại. Chi phí thấp hơn
một bậc và rủi ro kỹ thuật thấp hơn nhiều.

**AD-02 — AI không bao giờ truy cập trực tiếp cơ sở dữ liệu hoặc hệ thống nghiệp vụ**

*Phương án cân nhắc:* (a) cấp cho AI quyền sinh và chạy câu lệnh SQL trực tiếp; (b) AI chỉ
được gọi các tool định nghĩa sẵn, mỗi tool là một API nghiệp vụ có kiểm soát quyền.

*Lựa chọn:* phương án (b), không có ngoại lệ.

*Lý do:* Mô hình ngôn ngữ sinh văn bản theo xác suất; nếu cho phép nó sinh câu lệnh chạy trực
tiếp trên cơ sở dữ liệu thì mọi lỗi sinh văn bản đều có thể trở thành sự cố dữ liệu. Khi AI
chỉ được gọi tool, mỗi tool là một điểm kiểm soát: xác thực tham số, kiểm tra quyền, ghi nhật
ký, giới hạn phạm vi. Chi tiết ở Mục 5.3 và Mục 12.

**AD-03 — Tri thức tình huống lưu ở dạng có cấu trúc, không chỉ ở dạng văn bản**

*Phương án cân nhắc:* (a) lưu toàn bộ lịch sử hội thoại dưới dạng văn bản rồi để RAG tìm; (b)
xây riêng một mô hình dữ liệu tình huống kỹ thuật với các trường bắt buộc.

*Lựa chọn:* phương án (b) — trọng tâm của Mục 7.

*Lý do:* Một câu văn "dầm này nên tăng thép lên 8D25" không cho phép hệ thống lọc theo nhịp
dầm, cấp bê tông hay tải trọng. Dữ liệu có cấu trúc cho phép truy vấn chính xác, kiểm tra tính
hợp lệ, thống kê, và về lâu dài là phân tích xu hướng thiết kế. Đây chính là khác biệt giữa
một chatbot và một tài sản tri thức của doanh nghiệp.

**AD-04 — Con người phê duyệt là bước bắt buộc trong luồng, không phải tuỳ chọn**

*Phương án cân nhắc:* (a) AI đề xuất, kỹ sư tuỳ ý xem hoặc bỏ qua; (b) mọi kết quả đưa vào hồ
sơ đều phải qua thao tác phê duyệt có ghi nhận danh tính và thời điểm.

*Lựa chọn:* phương án (b).

*Lý do:* Trách nhiệm kỹ thuật thuộc về kỹ sư ký hồ sơ, không thuộc về phần mềm. Hệ thống phải
phản ánh đúng thực tế đó. Ngoài ra, chính thao tác phê duyệt là nguồn dữ liệu quý nhất: nó cho
biết đề xuất nào đúng, đề xuất nào bị bác, và vì sao.

**AD-05 — MCP là tầng tích hợp, không chứa logic nghiệp vụ**

*Phương án cân nhắc:* (a) viết logic tính toán ngay trong MCP server cho nhanh; (b) MCP server
chỉ là lớp vỏ mỏng, gọi xuống business service dùng chung.

*Lựa chọn:* phương án (b).

*Lý do:* Nếu logic nằm trong MCP server, công ty sẽ có hai bản logic tính toán khác nhau — một
cho ứng dụng web, một cho MCP — và theo thời gian chúng sẽ lệch nhau. Khi đó cùng một bài toán
cho hai kết quả, là tình huống không chấp nhận được trong hồ sơ kỹ thuật. Chi tiết ở Mục 11.

**AD-06 — Xây dựng theo giai đoạn có giá trị độc lập, không xây trọn gói một lần**

*Phương án cân nhắc:* (a) triển khai toàn bộ tính năng trong một dự án 12 tháng; (b) bốn giai
đoạn, mỗi giai đoạn tự nó đã mang lại giá trị sử dụng được.

*Lựa chọn:* phương án (b).

*Lý do:* Giai đoạn 1 — hỏi đáp tài liệu — đưa vào sử dụng được sau khoảng 3 tháng và tự nó đã
tiết kiệm thời gian tra cứu. Nếu giai đoạn 1 không được kỹ sư sử dụng, công ty dừng lại với
thiệt hại nhỏ, thay vì phát hiện điều đó sau 12 tháng đầu tư.

**AD-07 — PostgreSQL kèm pgvector cho giai đoạn đầu, tách vector store chuyên dụng khi cần**

*Phương án cân nhắc:* (a) dùng ngay OpenSearch hoặc một vector database chuyên dụng; (b) bắt
đầu với pgvector trên PostgreSQL, chuyển đổi khi vượt ngưỡng đã định nghĩa.

*Lựa chọn:* phương án (b), với điểm chuyển đổi nêu rõ ở Mục 10.

*Lý do:* Ở quy mô vài trăm nghìn đoạn văn bản, pgvector cho hiệu năng đủ tốt, và chỉ phải vận
hành một hệ quản trị dữ liệu duy nhất. Thêm một hệ thống lưu trữ thứ hai khi chưa cần là chi
phí vận hành không có lợi ích tương ứng.

**AD-08 — Ưu tiên độ tin cậy hơn độ bao phủ trong toàn bộ thiết kế**

*Phương án cân nhắc:* (a) hệ thống luôn cố trả lời mọi câu hỏi; (b) hệ thống được phép trả lời
"không tìm thấy căn cứ trong tài liệu nội bộ".

*Lựa chọn:* phương án (b).

*Lý do:* Một hệ thống trả lời sai một lần trong mười lần sẽ bị kỹ sư ngừng dùng vĩnh viễn, vì
chi phí kiểm tra lại lớn hơn chi phí tự tra cứu. Một hệ thống thẳng thắn nói "không có dữ
liệu" giữ được lòng tin và vẫn tiết kiệm thời gian ở chín lần còn lại.

---
