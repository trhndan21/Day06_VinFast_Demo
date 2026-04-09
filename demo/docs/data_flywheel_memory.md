# Data Flywheel & Memory Management

Hệ thống VinFast Auto-Agent có 2 luồng dữ liệu song song: **Memory** (ngắn hạn, trong session) và **Data Flywheel** (dài hạn, tích lũy feedback).

---

## 1️⃣ Memory Management (Trong Session)

### Tầng Lưu Trữ

```
STREAMLIT SESSION STATE
│
├─ messages[]                    # Tất cả tin nhắn (user + assistant)
│  ├─ {role, content, id, meta}
│  └─ Dùng để: hiển thị chat UI
│
├─ memory_cache[]                # Lịch sử được nén (1–3 lượt)
│  ├─ Lúc 1-2 lượt: raw text
│  │  ["User: VF 8 pin?\nAI: LFP 82kWh", "User: Sạc bao lâu?\nAI: 45 phút"]
│  │
│  └─ Lúc ≥3 lượt: summarized
│     ["Xe đang tư vấn: VinFast VF 8 Plus\nNội dung: Pin LFP, giá khoảng 1.1 tỷ..."]
│
└─ search_count                  # Biến đếm (0, 1, 2)
   └─ Dùng để: kiểm soát tool calling (max 2 lần)
```

### Quy Trình Cập Nhật Memory (app.py)

```
┌─────────────────────────────────────────────────────────────┐
│ LƯỢT 1: "VF 8 pin gì?"                                      │
├─────────────────────────────────────────────────────────────┤
│ 1. User input                                               │
│    → messages.append({role: "user", content: "VF 8 pin gì"})│
│                                                              │
│ 2. LangGraph invoke                                         │
│    input: "VF 8 pin gì?"                                    │
│    chat_history: [] (rỗng lần 1)                            │
│    → final_state: {answer: "Pin LFP 82kWh...", confidence}  │
│                                                              │
│ 3. Post-processing                                          │
│    → messages.append({role: "assistant", content: answer})  │
│    → Nếu answer tồn tại & không bị chặn:                   │
│       memory_cache.append("User: VF 8 pin gì?\nAI: Pin...")│
│       # memory_cache = [1 entry]                            │
│                                                              │
│ 4. UI render                                                │
│    → Hiển thị: "User: VF 8 pin gì?" + "AI: Pin LFP..."    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ LƯỢT 2: "Pin sạc bao lâu?"                                  │
├─────────────────────────────────────────────────────────────┤
│ 1. User input                                               │
│    → messages.append({role: "user", content: "Pin sạc..."}) │
│                                                              │
│ 2. LangGraph invoke                                         │
│    input: "Pin sạc bao lâu?"                                │
│    chat_history: [                                          │
│      "User: VF 8 pin gì?\nAI: Pin LFP 82kWh..."            │
│    ]  ← CONTEXT CÓ ĐÓ!                                     │
│    → Model biết đang tư vấn VF 8                            │
│    → final_state: {answer: "45 phút (10-70%)...", ...}    │
│                                                              │
│ 3. Post-processing                                          │
│    → messages.append({role: "assistant", content: answer})  │
│    → memory_cache.append("User: Pin sạc...\nAI: 45 phút...")│
│       # memory_cache = [2 entries]                          │
│                                                              │
│ 4. UI render                                                │
│    → Hiển thị: "User: Pin sạc...?" + "AI: 45 phút..."     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ LƯỢT 3: "Giá bao nhiêu?"                                    │
├─────────────────────────────────────────────────────────────┤
│ 1. User input → messages.append()                           │
│                                                              │
│ 2. LangGraph invoke                                         │
│    chat_history: [                                          │
│      "User: VF 8 pin gì?\nAI: Pin LFP...",                │
│      "User: Pin sạc..?\nAI: 45 phút..."                    │
│    ]  ← 2 lượt trước, model vẫn nhớ VF 8                   │
│    → final_state: {answer: "VF 8 Plus: 1.1 tỷ...", ...}  │
│                                                              │
│ 3. Post-processing                                          │
│    → memory_cache.append("User: Giá..?\nAI: 1.1 tỷ...")   │
│       # memory_cache.length = 3                             │
│       # ⚠️ ĐỦ ĐIỀU KIỆN NÉN!                              │
│                                                              │
│ 4. AUTO-SUMMARIZE                                           │
│    Gọi: summarize_memory([entry1, entry2, entry3])         │
│    LLM mini tóm tắt:                                        │
│      "Xe đang tư vấn: VinFast VF 8 Plus\n                 │
│       Nội dung: Khách quan tâm pin LFP, thời gian sạc      │
│       45 phút, giá khoảng 1.1 tỷ đồng."                    │
│                                                              │
│    → memory_cache = ["[SUMMARY] Xe: VF 8 Plus..."]        │
│       # Giảm từ 3 entries → 1 line tóm tắt                 │
│                                                              │
│ 5. UI render                                                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ LƯỢT 4: "Có bảo hành mấy năm?"                              │
├─────────────────────────────────────────────────────────────┤
│ 1. User input → messages.append()                           │
│                                                              │
│ 2. LangGraph invoke                                         │
│    chat_history: [                                          │
│      "[SUMMARY] Xe: VF 8 Plus, quan tâm pin + giá..."      │
│    ]  ← Context vẫn nhớ VF 8 (từ summary)                  │
│    → final_state: {answer: "Bảo hành 8 năm...", ...}      │
│                                                              │
│ 3. Post-processing                                          │
│    → memory_cache.append("User: Bảo hành..?\nAI: 8 năm...")│
│       # memory_cache = [summary, entry4] = 2 entries       │
│                                                              │
│ 4. UI render                                                │
└─────────────────────────────────────────────────────────────┘
```

### Logic Nén Bộ Nhớ (Pseudo-code)

```python
# app.py, dòng 160-167
if "answer" in final_state and not final_state.get("block_message"):
    # Lưu lượt mới vào memory
    turn = f"User: {prompt}\nAI: {final_state['answer']}"
    curr_session["memory_cache"].append(turn)
    
    # Kiểm tra điều kiện nén
    if len(curr_session["memory_cache"]) >= 3:
        # Gọi LLM mini tóm tắt
        summary = summarize_memory(curr_session["memory_cache"])
        
        # Thay thế 3 entries bằng 1 summary
        curr_session["memory_cache"] = [f"{summary}"]
```

### Tầm Quan Trọng của Memory

| Kịch bản | Nếu **KHÔNG** có memory | Nếu **CÓ** memory |
|----------|------------------------|------------------|
| Lượt 2: "Pin sạc bao lâu?" | Model chỉ biết câu này, không biết lượt 1 → **câu trả lời chung chung, mất ngữ cảnh VF 8** | Model biết câu 1 + 2 → **trả lời chuẩn, dành riêng cho VF 8** |
| Lượt 3: "Giá?" | Model lại quên VF 8, có thể nhầm thành VF 9 → **hallucination** | Model nhớ VF 8 từ 2 lượt trước → **trả lời đúng dòng xe** |
| Lượt 4+: "Bảo hành?" | Hoàn toàn quên context ban đầu | Summary giữ ngữ cảnh, model hiểu context đầy đủ |

---

## 2️⃣ Data Flywheel (Feedback Loop)

### Khái Niệm

Mỗi lần user bấm **👎 Sai**, hệ thống tự động log {prompt, response, label} → file JSONL. Dữ liệu này dùng để:
1. **Phân tích**: Xem model sai điểm nào thường xuyên
2. **Fine-tune**: Chuẩn bị training data cho v2.0
3. **Monitoring**: Theo dõi chất lượng hệ thống (tỉ lệ error)

### Luồng Feedback

```
┌──────────────────────────────────────────────────────┐
│ User đọc AI response                                 │
├──────────────────────────────────────────────────────┤
│ Nếu response sai/không hợp lệ                        │
│ → Bấm nút "👎 Sai"                                   │
│ (app.py, render_feedback function)                   │
└──────────────────────────────────────────────────────┘
                      ⬇
┌──────────────────────────────────────────────────────┐
│ app.py: Nút 👎 bấm                                   │
├──────────────────────────────────────────────────────┤
│ 1. Gọi: append_entry(                                │
│      user_prompt = "VF 8 giá bao nhiêu?",           │
│      response = "[AI BAD RESPONSE]",                │
│      label = "bad"                                   │
│    )                                                 │
│ 2. Cập nhật msg["label"] = "bad"                    │
│ 3. Toast: "✓ Đã ghi nhận đánh giá!"                │
└──────────────────────────────────────────────────────┘
                      ⬇
┌──────────────────────────────────────────────────────┐
│ logger.py: append_entry()                            │
├──────────────────────────────────────────────────────┤
│ 1. Mở file: data/training_data.jsonl                │
│ 2. Ghi dòng JSON:                                    │
│    {                                                 │
│      "prompt": "VF 8 giá bao nhiêu?",               │
│      "response": "[BAD RESPONSE]",                  │
│      "label": "bad",                                │
│      "timestamp": "2026-04-09T15:30:45"             │
│    }                                                 │
│ 3. Close file                                       │
└──────────────────────────────────────────────────────┘
                      ⬇
┌──────────────────────────────────────────────────────┐
│ data/training_data.jsonl                             │
├──────────────────────────────────────────────────────┤
│ {"prompt": "VF 8...", "response": "...", "label": "bad"} │
│ {"prompt": "VF 9...", "response": "...", "label": "good"} │
│ {"prompt": "Toyota...", "response": "...", "label": "blocked"} │
│ ... (tích lũy theo thời gian) ...                   │
└──────────────────────────────────────────────────────┘
                      ⬇
┌──────────────────────────────────────────────────────┐
│ Admin Dashboard (admin.py)                           │
├──────────────────────────────────────────────────────┤
│ • Đọc JSONL → hiển thị thống kê                      │
│ • Lọc: "bad", "good", "blocked"                     │
│ • Tìm pattern lỗi                                    │
│ • Export training set cho fine-tune                  │
└──────────────────────────────────────────────────────┘
                      ⬇
┌──────────────────────────────────────────────────────┐
│ Fine-tuning (Phase 6 tương lai)                      │
├──────────────────────────────────────────────────────┤
│ • Lọc "bad" labels → tạo training pairs             │
│ • Fine-tune gpt-4-turbo trên VinFast domain         │
│ • Deploy v2.0 → accuracy ↑, hallucination ↓        │
└──────────────────────────────────────────────────────┘
```

### Dữ Liệu JSONL (training_data.jsonl)

```jsonl
{"prompt": "VF 8 bản nào tốt nhất?", "response": "Pin LFP...", "label": "good", "timestamp": "2026-04-09T10:15:30"}
{"prompt": "VF 8 bản nào tốt nhất?", "response": "[WRONG RESPONSE]", "label": "bad", "timestamp": "2026-04-09T10:20:45"}
{"prompt": "Toyota Corolla so với VF 8?", "response": "[SPAM RESPONSE]", "label": "blocked", "timestamp": "2026-04-09T10:30:00"}
{"prompt": "Giao hàng ở Hà Nội không?", "response": "Dạ có giao...", "label": "good"}
{"prompt": "Xe bao nhiêu tiền?", "response": "[BAD PRICE INFO]", "label": "bad"}
... (tích lũy liên tục) ...
```

### Phân Tích Data Flywheel

```
METRICS
├─ Total responses: 1000
├─ Labeling distribution:
│  ├─ "good": 850 (85%) ✅ Model tốt
│  ├─ "bad": 120 (12%) ⚠️ Cần cải thiện
│  └─ "blocked": 30 (3%) 🛑 Spam, sensitive
│
└─ Common error patterns (từ "bad" labels):
   ├─ Sai thông số giá (VF 8 vs VF 9)
   ├─ Nhầm lẫn phiên bản (Plus vs Base)
   ├─ Model ảo giác về tính năng mới
   └─ Quên context sau lượt 2+
```

### Feedback Types

| Label | Ngữ cảnh | Ý Nghĩa |
|-------|----------|---------|
| **good** | User bấm 👍 | Response chính xác, hữu ích |
| **bad** | User bấm 👎 | Response sai, incomplete, hallucination |
| **blocked** | Guardrail chặn | Query spam, off-topic, hoặc sensitive |
| **lead** | User gửi booking form | Khách quan tâm, muốn tư vấn viên liên hệ |

---

## 3️⃣ Tích Hợp Memory + Data Flywheel

```
┌─────────────────────────────────────────────────────┐
│ SESSION FLOW                                        │
├─────────────────────────────────────────────────────┤
│ Lượt 1                                              │
│ ├─ memory_cache = []                                │
│ ├─ Input: prompt1 → LLM (no context)               │
│ ├─ Output: answer1 → memory_cache += [entry1]      │
│ └─ User: 👍 → log {prompt1, answer1, "good"}      │
│                                                     │
│ Lượt 2                                              │
│ ├─ memory_cache = [entry1]                          │
│ ├─ Input: prompt2 + chat_history [entry1]          │
│ │   → LLM **CÓ** context from entry1               │
│ ├─ Output: answer2 → memory_cache += [entry2]      │
│ └─ User: 👎 → log {prompt2, answer2, "bad"}       │
│                                                     │
│ Lượt 3                                              │
│ ├─ memory_cache = [entry1, entry2]                  │
│ ├─ Input: prompt3 + chat_history [entry1, entry2]  │
│ │   → LLM **CÓ** full context (2 lượt trước)       │
│ ├─ Output: answer3 → memory_cache += [entry3]      │
│ │   → len(memory_cache) >= 3 → SUMMARIZE           │
│ ├─ memory_cache = [summary]                         │
│ └─ User: 👍 → log {prompt3, answer3, "good"}       │
│                                                     │
│ Lượt 4+                                             │
│ ├─ memory_cache = [summary]  ← context vẫn cô đặc  │
│ ├─ Input: prompt4 + chat_history [summary]         │
│ │   → LLM **CÓ** essence từ summary                │
│ ├─ Output: answer4                                  │
│ └─ Feedback → log training_data.jsonl              │
└─────────────────────────────────────────────────────┘

        ⬇ (Sau khi có đủ feedback)
        
┌─────────────────────────────────────────────────────┐
│ ADMIN REVIEW & FINE-TUNE                            │
├─────────────────────────────────────────────────────┤
│ 1. Admin dashboard đọc training_data.jsonl          │
│ 2. Phân tích: bad responses đều sai điểm gì?      │
│    → Ví dụ: model hay nhầm VF 8 vs VF 9           │
│ 3. Tạo training set từ "bad" labels                │
│    {prompt: "VF 8...", output: "[CORRECT ANSWER]"} │
│ 4. Fine-tune gpt-4-turbo (OpenAI API)              │
│ 5. Deploy v2.0                                      │
│    → Accuracy ↑, Hallucination ↓, Recall ↑        │
└─────────────────────────────────────────────────────┘
```

---

## 🎯 Tóm Tắt

| Khía Cạnh | Mục Đích | Phạm Vi |
|-----------|----------|---------|
| **Memory (Ngắn hạn)** | Giữ context trong một conversation | 1 session, 1–3 lượt (sau nén) |
| **Data Flywheel** | Thu thập feedback để cải tiến model | Dài hạn, tích lũy hàng ngày |
| **Auto-summarize** | Nén bộ nhớ → giảm token, giữ context | Kích hoạt lúc ≥3 lượt |
| **Feedback buttons** | Ghi nhãn response → training data | Mỗi lượt assistant |

**Kết quả**: Hệ thống vừa **nhớ ngữ cảnh tốt** (trong session), vừa **học từ lỗi** (qua Data Flywheel) → **chất lượng AI tăng theo thời gian**.
