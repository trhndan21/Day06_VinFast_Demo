# VinFast Auto-Agent Demo

Web app tư vấn xe VinFast 24/7 bằng AI ReAct Agent. Kiến trúc Dual-LLM (gpt-4o-mini + gpt-4-turbo), tool calling (Tavily search tối đa 2 lần), multi-session memory, guardrails, và data flywheel cho fine-tuning.

## Cấu Trúc Thư Mục

```
demo/
├── data/
│   └── training_data.jsonl      # Feedback data từ 👎 Sai: {prompt, response, label}
├── .streamlit/
│   └── secrets.toml             # API keys (OPENAI, TAVILY)
│
├── app.py                       # Streamlit Frontend
│   ├─ Multi-session chat UI
│   ├─ Memory cache (1–3 lượt) + auto-summarize
│   ├─ Confidence-based booking modal
│   └─ Feedback buttons (👍 Tốt / 👎 Sai)
│
├── engine.py                    # LangGraph ReAct Engine
│   ├─ guardrail: Lọc nội dung (LLM mini)
│   ├─ reasoning: Suy luận + bind tool (LLM main, max 2 search)
│   ├─ tools: Tavily search executor
│   ├─ parse_answer: Parse JSON trả lời
│   └─ summarize_memory(): Nén lịch sử
│
├── search.py                    # Tavily Search API wrapper
│   └─ search_tavily(): VinFast + query → snippets + URLs
│
├── logger.py                    # Data Flywheel logger
│   └─ append_entry(): Log {prompt, response, label} → JSONL
│
├── admin.py                     # Admin Dashboard (Phase 5)
├── main.py                      # st.navigation multipage router
├── constants.py                 # System prompts + guardrail rules
└── requirements.txt
```

## 🚀 Cài Đặt & Chạy

### 1️⃣ Virtual Environment
```bash
cd demo
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
```

### 2️⃣ Dependencies
```bash
pip install -r requirements.txt
```

### 3️⃣ API Keys
Tạo `demo/.streamlit/secrets.toml`:
```toml
OPENAI_API_KEY = "sk-..."
TAVILY_API_KEY = "tvly-..."
```

Hoặc export trước khi chạy:
```bash
export OPENAI_API_KEY="sk-..."
export TAVILY_API_KEY="tvly-..."
```

### 4️⃣ Run
```bash
streamlit run app.py
```
Ứng dụng sẽ mở tại `http://localhost:8501`

---

## 📊 Luồng Hoạt Động

```
User nhập prompt
    ⬇
Streamlit: Fetch memory_cache + invoke agent_app
    ⬇
LangGraph (engine.py):
  [guardrail] → [reasoning ↔ tools (max 2x)] → [parse_answer]
    ⬇
Post-processing (app.py):
  • Hiển thị answer + confidence
  • confidence < 7 → gợi booking
  • Feedback 👍/👎 → logger
  • Lưu memory_cache + auto-summarize (≥3 lượt)
    ⬇
Data Flywheel: training_data.jsonl (fine-tune data)
```

---

## 🔑 Tính Năng Chính

| Tính năng | Mô tả |
|----------|-------|
| **Multi-session Chat** | Mỗi session độc lập (messages, memory_cache, search_count) |
| **Memory Management** | Lưu 1–3 lượt + auto-summarize với LLM mini |
| **Guardrail** | Lọc OFF_TOPIC / SENSITIVE / COMPETITOR spam |
| **Tool Calling** | Tavily search, tối đa 2 lần/lượt (search_count < 2) |
| **Confidence-based UI** | Nếu confidence < 7 → thẻ cảnh báo + nút gọi tư vấn viên |
| **Data Flywheel** | Mỗi 👎 Sai tự động log → training_data.jsonl |
| **Feedback Loop** | Nút 👍/👎 dưới mỗi tin nhắn AI → label + insert DB |

---

## 📁 File Quan Trọng

- **app.py**: Giao diện Streamlit chính, quản lý UI + state + memory
- **engine.py**: LangGraph workflow (guardrail → reasoning ↔ tools → parse)
- **constants.py**: System prompts, guardrail rules, thresholds
- **search.py**: Tavily wrapper, chuẩn hóa query
- **logger.py**: Ghi log feedback vào JSONL (Data Flywheel)

---

## 🧪 Testing

Xem file `test_cases.md` để danh sách test case chi tiết (happy path, low confidence, failure, correction).
