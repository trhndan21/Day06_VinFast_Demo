# SPEC — VinFast AI Product (draft / `demo/docs`)

> Nháp làm việc. SPEC nộp LMS dùng bản nhóm (vd. `Nhom30-403-Day06/spec-final.md`). Đối chiếu code `demo/` trước khi dùng số liệu hay tên model ở đây.

**Nhóm:** 30-403-Day05
**Track:** VinFast
**Problem statement (1 câu):** *Khách hàng tìm hiểu mua xe VinFast gặp khó khăn khi tra cứu thông số, chính sách và thường phải chờ đợi lâu ngoài giờ hành chính mới được hỗ trợ; Web app tư vấn AI độc lập Auto-Agent hoạt động 24/7, ứng dụng mô hình ReAct Tool Calling kết hợp Trí nhớ Đa luồng (Multi-session Memory) để trả lời chính xác, chặn lọc nội dung độc hại qua Guardrails, và thu thập Data Sale.*

---

## 1. AI Product Canvas

|   | Value | Trust | Feasibility |
|---|-------|-------|-------------|
| **Câu hỏi** | User nào? Pain gì? AI giải gì? | Khi AI sai thì sao? User sửa bằng cách nào? | Cost/latency bao nhiêu? Risk chính? |
| **Trả lời** | *Khách muốn mua xe. Pain: Hỏi đáp thông số lẻ tẻ chờ CSKH quá lâu. AI giải: Phản hồi siêu tốc qua tự tra cứu bằng Search Tool.* | *Khi AI tìm nhầm thông tin dòng xe, nó tự hạ điểm Confidence, hiện thẻ Vàng cảnh báo sai lệch và cung cấp nút kết nối Sale thật. User báo sai bằng Thumbs Down.* | *Latency <5s do chạy ReAct vòng lặp. Giữ phí bằng gpt-4o-mini (guardrail) kết hợp gpt-4-turbo (reasoning). Risk: Rơi vào vòng lặp tìm kiếm vô tận.* |

**Automation hay augmentation?** ☐ Automation · ☑ Augmentation
Justify: *Augmentation — Trợ lý AI chỉ giải quyết phễu tư vấn tò mò (L1 Support). Ngay khi chạm vào kiến thức pháp lý quá ngách hoặc người dùng thể hiện ý muốn lên lịch (Booking Mode), hệ thống chuyển quyền quyết định và tư vấn chuyên sâu cho Tư vấn viên hãng.*

**Learning signal:**
1. User correction đi vào đâu? *Nút feedback “👎 Sai” ở mỗi tin nhắn sẽ log dữ liệu thẳng vào DB (file jsonl), kèm theo đúng Câu Hỏi (Prompt) làm gốc.*
2. Product thu signal gì để biết tốt lên hay tệ đi? *Tỉ lệ hiển thị "Thẻ Cảnh Báo Không Tự Tin" giảm, tỉ lệ khách chịu để lại thông tin Booking tăng lên.*
3. Data thuộc loại nào? ☐ User-specific · ☑ Domain-specific · ☐ Real-time · ☐ Human-judgment · ☐ Khác: ___
   Có marginal value không? *Có. Mô hình AI Base không rành chi tiết giá xe VinFast hoặc cấu hình bị đổi mới hàng tháng. Việc Search cập nhật real-time mang lại value chốt đơn cao nhất.*

---

## 2. User Stories — 4 paths

### Feature: *Chatbot tư vấn xe Auto-Agent*

**Trigger:** *Khách hàng nhập vào ô Chat: "Tư vấn cho mình VF 8"*

| Path | Câu hỏi thiết kế | Mô tả |
|------|-------------------|-------|
| Happy — AI đúng, tự tin | User thấy gì? Flow kết thúc ra sao? | *AI tham chiếu Memory cũ, quyết định tự Call hàm `search_web_tool` tìm thông số. Trả lời ngay tắp lự, kèm trích dẫn thẻ Link và câu hỏi dẫn dắt thêm.* |
| Low-confidence — AI không chắc | System báo "không chắc" bằng cách nào? User quyết thế nào? | *Tavily không bắt được thông số (VD giá mật). AI tính toán độ tin cậy < 7. Thay mặt hãng, AI nhẹ nhàng từ chối (không bịa data) và chủ động trỏ chuột hiện 1 thẻ UI Cảnh báo + Nút "📞 Gọi tư vấn viên" ra giữa màn hình.* |
| Failure — AI sai | User biết AI sai bằng cách nào? Recover ra sao? | *Nếu AI bị ảo giác, User đọc và thấy sai, có thể bấm nút "👎 Sai" trực quan ngay dưới tin nhắn. Dữ liệu hội thoại lưu vào hệ thống Data Flywheel để kỹ sư Dev sau này Tinh chỉnh (Fine-tune).* |
| Correction — user sửa | User sửa bằng cách nào? Data đó đi vào đâu? | *Chỉ bằng 1 click Thumbs Down, log file Jsonl (chứa prompt và bad response) sẽ được ghi nhận làm Human Feedback thẳng lên Dashboard Admin, không bắt User phải nhập form dài.* |

---

## 3. Eval metrics + threshold

**Optimize precision hay recall?** ☑ Precision · ☐ Recall
Tại sao? *Uy tín hãng xe là vô giá. Nếu cung cấp sai giá xe, sai thông số Pin sẽ làm khách khiếu nại. Thà AI báo "Không biết - Mời gọi Tư vấn" (Low recall) còn hơn đưa nhầm data của VF 9 cho VF 8.*

| Metric | Threshold | Red flag (dừng khi) |
|--------|-----------|---------------------|
| *Answer Accuracy (Cung cấp chuẩn thông số từng Dòng Xe)* | *≥ 98%* | *< 85% (ReAct Agent bị lỗi không gọi được Web Search).* |
| *Tool Loop Escape Rate (Tỉ lệ tự thoát hỏi vòng lặp Search vô tận)* | *100%* | *Chạm mốc 0% (Hệ thống ReAct lỗi, không enforce tối đa 2 lần search).* |
| *Low-Confidence Trigger (Tỉ lệ chuyển luồng khi mù mờ)* | *≥ 90%* | *< 50% (Hệ thống bị "ảo giác" tự tin quá mức)* |

---

## 4. Top 3 failure modes

| # | Trigger | Hậu quả | Mitigation |
|---|---------|---------|------------|
| 1 | *Tìm kiếm Search lẫn lộn kết quả phân tích nhiều dòng xe.* | *Lấy thông số VF 9 áp dụng để tư vấn cho VF 8 (Hallucination)* | *Bọc hệ Dual-LLM: Mini LLM viết lại Query chứa đúng tên xe + Main LLM chạy cơ chế Chain-of-Thought (Target_car validation), nếu check lệch xe -> Hủy dữ liệu ngay.* |
| 2 | *Hệ thống mắc kẹt trong vòng lặp Tool Calling tự động (ReAct).* | *UI bị treo Loading, tốn kém hàng vạn Token do LLM cứ tra Google liên tục tìm 1 câu hỏi trên trời.* | *Cài biến bảo vệ `search_count < 2`: Tool chỉ được kích hoạt tối đa 2 lần (search 0 hoặc 1). Sau đó hệ thống unbind Tool, ép AI tự tổng kết dữ liệu khép lại luồng.* |
| 3 | *Khách spam câu hỏi công kích, châm chọc đối thủ.* | *AI vô tình nói xấu các hãng xe Toyota, Tesla làm xấu mặt hình ảnh hãng.* | *Dựng ngay Trạm Vệ binh (Guardrail Node) bằng Prompt cứng sử dụng mô hình Mini. Lọc và khóa chết (Block) tất cả chuỗi hỏi đáp Sensitive và Competitor.* |

---

## 5. ROI 3 kịch bản

|   | Conservative | Realistic | Optimistic |
|---|-------------|-----------|------------|
| **Assumption** | *200 khách/ngày dùng Chatbot* | *1000 khách/ngày* | *4000 khách/ngày* |
| **Cost** | *~$5/ngày (Inference LLM 2 tầng)* | *~$18/ngày* | *~$50/ngày* |
| **Benefit** | *Giải đáp tức thì, tiết kiệm 5h CSKH.* | *Thay thế 5 nhân viên Sale L1, tạo ra 50 khách ngách chốt deal.* | *Thống trị mạng lưới L1, lọc được 300 Lead Booking rất nét.* |
| **Net** | *Chủ yếu lấy feedback AI* | *Dương mạnh cả Branding và Sale* | *Bùng nổ doanh số xe từ tư vấn tự động* |

---

## 6. Mini AI spec (1 trang)

**1. Sản phẩm & Giải pháp:**
VinFast Auto-Agent có kiến trúc ReAct Agent (Dual-LLM). LLM nhẹ (`gpt-4o-mini`) làm trạm gác + nén bộ nhớ. LLM Lớn (`gpt-4-turbo`) làm đầu não, được trang bị Tool Gọi hàm (Search Tavily, tối đa 2 lần). Hệ thống có UI đa luồng (Multi-session) đảm bảo môi trường Chat cách ly tuyệt đối.

**2. Khách hàng/User:**
Khách đang tìm xe hoặc ngắm nghía tham khảo cấu hình, khách không muốn bị nhân viên Sale gọi điện làm phiền quá sớm nhờ trợ lý tự động phân tích giúp.

**3. Bản chất sản phẩm (Auto/Aug):**
Augmentation (Phễu lọc đầu). Giải quyết siêu tốc các câu hỏi về thông số, giá lăn bánh, màu xe... Bắt sóng "chưa tự tin" ngay lập tức để đẩy UI gọi nhân sự (Tư vấn viên) thu thập Form Booking.

**4. Metrics & Quality Trade-offs:**
**Precision > Recall**. Sự an toàn của tên dòng xe (Target Car Context) là tối thượng. Bộ nhớ Memory được nén ngầm theo luật Few-shot để khắc vĩnh viễn Tên Xe đang tư vấn vào bộ nhớ trung hạn, giúp Search Tool không bao giờ tìm chệch hướng mục tiêu. 

**5. Cơ chế Data Flywheel:**
Xây dựng nút Thumbs Up/Down ở mỗi block tin nhắn. Mọi báo lỗi (👎 Sai) lập tức kích hoạt luồng log vào file `training_data.jsonl`, ghép nối hoàn hảo với prompt đầu vào tạo thành cặp Data chuẩn hóa, sẵn sàng cho kỹ sư Fine-tune ở chu kỳ Deploy thế hệ AI sau.
