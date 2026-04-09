# VinFast Auto-Agent — Luồng Xử Lý Đầu Cuối

## 📊 Sơ Đồ Tổng Quan (Từ Trên Xuống Dưới)

```
┌──────────────────────────────────────────────────────────────────────┐
│ 1️⃣  STREAMLIT APP (app.py)                                          │
│ ├─ Nhập: prompt từ người dùng                                       │
│ ├─ Lấy: memory_cache (lịch sử 1–3 lượt, hoặc tóm tắt)            │
│ └─ Gửi: {input, chat_history} → agent_app.invoke() (search_count khởi tạo trong graph)│
└──────────────────────────────────────────────────────────────────────┘
                              ⬇
┌──────────────────────────────────────────────────────────────────────┐
│ 2️⃣  LANGGRAPH STATE MACHINE (engine.py)                             │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ 🚨 GUARDRAIL NODE                                             │ │
│  │ ├─ Input: state.input                                         │ │
│  │ ├─ LLM mini (`GUARDRAIL_MODEL` trong constants.py): phân loại JSON │ │
│  │ ├─ Kiểm tra: OFF_TOPIC / SENSITIVE / ...                     │ │
│  │ └─ Output: category + block_message                           │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                  ⬇ (CONDITIONAL: category == PASS?)                │
│       ┌─────────────────────┬─────────────────────┐               │
│       │                     │                     │               │
│      ❌ Không PASS        ✅ PASS                │               │
│       │                     │                     │               │
│       ⬇                     ⬇                     ⬇               │
│  ┌──────────────────┐ ┌──────────────────────────────────────┐   │
│  │ 🛑 END (Block)   │ │ 🧠 REASONING NODE                    │   │
│  │ Trả:             │ │ ├─ Init: search_count = 0            │   │
│  │ block_message    │ │ ├─ Gộp: system + history + input     │   │
│  └──────────────────┘ │ ├─ IF search_count < 2:              │   │
│                       │ │    Bind tool search_web_tool       │   │
│                       │ ├─ LLM chính (`REASONING_MODEL`): invoke() │   │
│                       │ └─ Output: AIMessage (có/không tool) │   │
│                       └──────────────────────────────────────┘   │
│                             ⬇ (CONDITIONAL: có tool_calls?)       │
│                    ┌────────────────────┬──────────┐              │
│                    │                    │          │              │
│                 ✅ Có            ❌ Không       │              │
│                    │                    │          │              │
│                    ⬇                    ⬇          ⬇              │
│         ┌────────────────────┐  ┌──────────────────────────┐     │
│         │ 🔍 TOOLS NODE      │  │ 📋 PARSE_ANSWER         │     │
│         │ ├─ search_count++  │  │ ├─ Parse JSON response  │     │
│         │ │  (0→1 hoặc 1→2)  │  │ ├─ Extract: answer,     │     │
│         │ ├─ Tavily search   │  │ │  confidence, URL,      │     │
│         │ │  "VinFast" query │  │ │  suggest_human         │     │
│         │ ├─ → ToolMessage   │  │ └─ Output: parsed data   │     │
│         │ └─ messages stack++│  └──────────────────────────┘     │
│         └────────────────────┘             ⬇                     │
│               ⬇                     ┌──────────────────┐         │
│         ┌─────────────────┐         │ 🛑 END (Answer)  │         │
│         │ ⬅️ QUAY LẠI     │         │ Trả: answer,     │         │
│         │ REASONING NODE  │         │ confidence, ...  │         │
│         │                 │         └──────────────────┘         │
│         │ (Lần thứ 2)     │                                      │
│         └────────────┬────┘                                      │
│                      │                                           │
│      🔄 Vòng lặp tiếp tục cho đến khi model không gọi tool     │
│         hoặc search_count ≥ 2 → chuyển sang parse_answer        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              ⬇
┌──────────────────────────────────────────────────────────────────────┐
│ 3️⃣  POST-PROCESSING (app.py)                                        │
│ ├─ final_state = {answer, confidence, source_url, ...}              │
│ ├─ Nếu blocked: hiển thị block_message, log "blocked"               │
│ ├─ Nếu answer:                                                      │
│ │  ├─ Hiển thị answer                                              │
│ │  ├─ Đánh giá: final_state.suggest_human → card tư vấn (engine: chủ yếu confidence < 7) │
│ │  └─ Nút feedback: 👍 Tốt / 👎 Sai                               │
│ ├─ Cập nhật memory_cache: lưu (prompt + answer)                    │
│ ├─ Nén bộ nhớ: khi memory_cache >= 3 lượt → summarize_memory()   │
│ └─ Render: hiển thị trên Streamlit, rerun() cho lượt tiếp theo   │
└──────────────────────────────────────────────────────────────────────┘
```

### 🔁 Chi Tiết Vòng Lặp Tool Calling

```
REASONING (search_count=0)
    ├─ Bind tool ✅ (0 < 2)
    ├─ Model quyết định gọi search
    ⬇
TOOLS (search_count → 1)
    ├─ Thực thi Tavily
    ├─ Trả ToolMessage
    ⬇
REASONING (search_count=1)
    ├─ Bind tool ✅ (1 < 2)
    ├─ Model quyết định gọi search lần 2
    ⬇
TOOLS (search_count → 2)
    ├─ Thực thi Tavily
    ├─ Trả ToolMessage
    ⬇
REASONING (search_count=2)
    ├─ Unbind tool ❌ (2 < 2 sai)
    ├─ Model chỉ có thể trả JSON (không tool)
    ⬇
PARSE_ANSWER
    ├─ Parse & trích dữ liệu
    ⬇
END
```

---

## 📋 Chi Tiết Từng Thành Phần

### 1️⃣ **Streamlit Frontend** (`app.py`)

| Tính năng | Mô tả |
|-----------|-------|
| **Session** | Mỗi tab/người dùng có session_id, danh sách messages, memory_cache riêng |
| **Chat history** | Tất cả tin nhắn (user + assistant) lưu trong `messages[]` |
| **Memory cache** | Tóm tắt lịch sử gần nhất (1–3 lượt): `[f"User: ...\nAI: ..."]` |
| **Feedback** | Nút 👍/👎 sau mỗi câu trả lời → log vào database (append_entry) |
| **Auto-summarize** | Khi memory_cache >= 3 lượt → gọi `summarize_memory()` → nén thành 1 dòng |

---

### 2️⃣ **LangGraph Workflow** (`engine.py`)

#### **Cấu Trúc State**
```python
class AgentState(TypedDict):
    input: str              # Câu hỏi hiện tại
    chat_history: List[str] # Lịch sử từ Streamlit
    messages: List          # LangGraph message stack
    category: str           # PASS / OFF_TOPIC / SENSITIVE / ...
    block_message: str | None  # Thông báo chặn nếu không PASS
    search_count: int       # Số lần gọi Tavily (max ~2)
    answer: str             # Trả lời cuối
    confidence: int         # Độ tin cậy (0–10)
    source_url: str         # URL nguồn
    suggest_human: bool     # Gợi ý cần tư vấn viên
    suggest_reason: str     # Lý do gợi ý
```

#### **4 Node Chính**

| Node | Hành động | Input | Output |
|------|-----------|-------|--------|
| **guardrail** | Lọc nội dung bằng LLM mini (`GUARDRAIL_MODEL`) | input | category, block_message |
| **reasoning** | Gọi LLM chính (`REASONING_MODEL`), bind tool search tối đa 2 lần (search_count < 2) | messages, search_count | AIMessage (có thể tool_calls) |
| **tools** | Thực thi Tavily search, trả ToolMessage, tăng search_count từ 0→1→2 | tool_calls | ToolMessage[], search_count++ |
| **parse_answer** | Trích JSON từ AIMessage cuối cùng | messages | answer, confidence, source_url, suggest_human |

#### **Luồng Điều Kiện**
- **Sau guardrail**: category ≠ PASS → END (trả block_message); PASS → reasoning
- **Sau reasoning**: có tool_calls → tools; không → parse_answer
- **Sau tools**: quay lại reasoning (vòng lặp)
- **Sau parse_answer**: END

---

### 3️⃣ **Tìm Kiếm & Công Cụ** (`search.py`)

| Công cụ | Việc làm |
|---------|----------|
| **Tavily API** | Web search với từ khóa `"VinFast " + query` |
| **Kết quả** | 3 snippets + 3 URLs → trả về trong ToolMessage |

---

### 4️⃣ **Quản Lý Bộ Nhớ** (`app.py` + `engine.py`)

```
Lượt 1: User: "VF 8 pin gì?"
        AI: "Pin LFP 82kWh / NMC 75kWh"
        → memory_cache = ["User: VF 8 pin gì?\nAI: Pin ..."]

Lượt 2: User: "Pin sạc bao lâu?"
        → chat_history = memory_cache (lịch sử có VF 8!)
        → Model biết context → trả đúng
        → memory_cache = ["...", "User: Pin sạc ...\nAI: ..."]

Lượt 3: (tương tự, memory_cache = 3 lượt)

Lượt 4: memory_cache.length >= 3
        → summarize_memory() bằng LLM mini
        → Tóm tắt: "Xe đang tư vấn: VF 8\nNội dung: ..."
        → memory_cache = ["Tóm tắt\nNội dung: ..."]
        → Quay lại lưu lượt 4, 5, ...
```

**Tầm quan trọng**: Nếu không lưu memory (BUG cũ), model chỉ thấy câu hiện tại, quên ngữ cảnh.

---

### 5️⃣ **Độ Tin Cậy & Gợi Ý** (parse_answer → app.py)

- Trong `node_parse_answer`: `suggest_human` đặt true khi `confidence < CONFIDENCE_THRESHOLD` (7); JSON có thể có `suggest_reason` để hiển thị kèm card (nếu UI dùng).
- App hiện nút "📞 Gọi tư vấn viên" khi `final_state.suggest_human`.
- Lead submit form → `append_entry(..., label="lead")` → JSONL, không phải DB.

---

## 🔗 Luồng Tóm Tắt (Đầu Cuối)

```
[User gõ] → Streamlit
    ↓
[Fetch memory_cache] → {input, chat_history}
    ↓
[agent_app.invoke()] → LangGraph
    ├─ guardrail (chặn/pass)
    ├─ reasoning (→ tools ↔ reasoning lặp)
    └─ parse_answer (trích JSON)
    ↓
[final_state] → {answer, confidence, ...}
    ↓
[Hiển thị + lưu memory] → Streamlit UI
    ↓
[Tóm tắt nếu >= 3 lượt] → memory_cache tối ưu
```
