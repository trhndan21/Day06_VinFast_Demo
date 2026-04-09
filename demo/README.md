# VinFast Auto-Agent Demo

Web app tư vấn xe VinFast 24/7 bằng LangGraph + tool calling. Kiến trúc dual-LLM: model guardrail và model reasoning lấy từ `constants.py` (hiện `GUARDRAIL_MODEL` / `REASONING_MODEL`, ví dụ `gpt-5.4-mini` + `gpt-5.4`). Tavily search tối đa 2 lần/lượt, multi-session memory, guardrails, data flywheel (JSONL).

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
streamlit run main.py
# hoặc chỉ chat: streamlit run app.py
```
Ứng dụng sẽ mở tại `http://localhost:8501` (`main.py` mở multipage: Chat + Admin).

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
  • Hiển thị answer + confidence (+ meta nếu có)
  • `final_state.suggest_human` true (trong `engine`: chủ yếu khi `confidence` < `CONFIDENCE_THRESHOLD`, 7) → card gợi tư vấn + form lead
  • Feedback 👍/👎 → `logger.append_entry` → file JSONL
  • Lưu memory_cache + auto-summarize (≥3 lượt)
    ⬇
Data Flywheel: training_data.jsonl (fine-tune data)
```

---

## 🔑 Tính Năng Chính

| Tính năng | Mô tả |
|----------|-------|
| **Multi-session Chat** | Mỗi session độc lập (`messages`, `memory_cache`); `search_count` là trong LangGraph mỗi lượt `invoke`, không lưu trong `session_state` |
| **Memory Management** | Lưu 1–3 lượt + auto-summarize với LLM mini |
| **Guardrail** | Lọc OFF_TOPIC / SENSITIVE / COMPETITOR spam |
| **Tool Calling** | Tavily search, tối đa 2 lần/lượt (search_count < 2) |
| **Gợi tư vấn viên** | `suggest_human` sau parse (hiện gắn với `confidence` < 7) → thẻ cảnh báo + nút gọi tư vấn viên |
| **Data Flywheel** | 👍/👎/lead/blocked → append `data/training_data.jsonl` |
| **Feedback Loop** | Nút 👍/👎 dưới tin assistant → `label` trong JSONL (không qua DB) |

---

## 📁 File Quan Trọng

- **app.py**: Giao diện Streamlit chính, quản lý UI + state + memory
- **engine.py**: LangGraph workflow (guardrail → reasoning ↔ tools → parse)
- **constants.py**: System prompts, guardrail rules, thresholds
- **search.py**: Tavily wrapper, chuẩn hóa query
- **logger.py**: Ghi log feedback vào JSONL (Data Flywheel)

---

## 🧪 Testing

Xem `docs/test_cases.md` — lưu ý vài kịch bản có thể mô tả UX “IDEAL”; đối chiếu `app.py` trước khi coi là pass/fail.
