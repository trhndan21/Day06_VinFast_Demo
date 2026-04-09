# Phase 1 — Chat UI (`app.py`)

> Đọc `CONTEXT.md` trước. File này chỉ mô tả phần Phase 1 đảm nhiệm.

---

## Nhiệm vụ

Xây dựng `app.py` — Streamlit main app:
- Chat UI: `st.chat_message` + `st.chat_input`
- Gọi đến `agent_app.invoke(initial_state)` (từ Phase 2 - LangGraph) để lấy output.
- Render suggest card inline trong chat (nếu `suggest_human = True`)
- Booking flow (form thu thập thông tin để đặt lịch)

---

## Skeleton `app.py`

```python
import streamlit as st
import uuid
from constants import *
from engine import agent_app
from logger import append_entry

st.set_page_config(page_title="VinFast Auto-Agent", page_icon="🚗", layout="centered")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "booking_mode" not in st.session_state:
    st.session_state.booking_mode = False
```

---

## UI Layout

```python
st.title("🚗 VinFast Auto-Agent")
st.caption("Trợ lý tư vấn xe độc lập (Giả lập) • Được hỗ trợ bởi LangGraph")
st.divider()

# Hiển thị lịch sử chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        # Nếu đang ở block message (guardrail block)
        if msg.get("blocked"):
            continue

        if msg.get("suggest_reason"):
            render_suggest_card(msg["suggest_reason"], msg["id"])

        if msg["role"] == "assistant" and not msg.get("label"):
            render_feedback(msg)
```

---

## Xử lý User Input (Gọi LangGraph)

```python
if prompt := st.chat_input("Hỏi về xe VinFast..."):
    st.session_state.messages.append({"role": "user", "content": prompt, "id": str(uuid.uuid4())})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Đang tìm kiếm thông tin..."):
            
            # --- Gọi LangGraph Engine ---
            final_state = agent_app.invoke({"input": prompt})
            
            msg_id = str(uuid.uuid4())
            response_msg = {
                "id": msg_id,
                "role": "assistant"
            }

            # Xử lý nếu bị Guardrail Block
            if final_state.get("block_message"):
                response_msg["content"] = final_state["block_message"]
                response_msg["blocked"] = True
                append_entry(prompt, final_state["block_message"], "blocked")
            else:
                # Xử lý Flow Thành công (Cache Hit hoặc Reasoning)
                response_msg["content"] = final_state["answer"]
                response_msg["meta"] = {
                    "confidence": final_state["confidence"],
                    "source_url": final_state.get("source_url", "")
                }
                
                # Hiển thị nội dung Answer
                st.markdown(final_state["answer"])
                
                # Kiểm tra cờ suggest human
                if final_state.get("suggest_human"):
                    response_msg["suggest_reason"] = final_state["suggest_reason"]
                    render_suggest_card(final_state["suggest_reason"], msg_id)
                
                render_feedback(response_msg)

    st.session_state.messages.append(response_msg)
    st.rerun()
```

---

## Render Component Phụ

```python
def render_suggest_card(reason, msg_id):
    with st.container(border=True):
        st.warning(f"⚠️ **Em chưa chắc vì:** {reason}")
        st.write("Anh/chị có muốn em kết nối với tư vấn viên VinFast không?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📞 Gọi tư vấn viên", key=f"consult_{msg_id}"):
                st.session_state.booking_mode = True
                st.rerun()
        with col2:
            st.button("Tiếp tục chat", key=f"skip_{msg_id}")

def render_feedback(msg):
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("👍 Tốt", key=f"good_{msg['id']}"):
            append_entry(st.session_state.messages[-2]["content"], msg["content"], "good")
            msg["label"] = "good"
            st.toast("✓ Cảm ơn phản hồi!", icon="✅")
    with col2:
        if st.button("👎 Sai", key=f"bad_{msg['id']}"):
            msg["show_correction"] = True
            st.rerun()

    if msg.get("show_correction"):
        correction = st.text_input("Câu đúng là gì? (tuỳ chọn)", key=f"corr_{msg['id']}")
        if st.button("Gửi báo lỗi", key=f"submit_{msg['id']}"):
            append_entry(st.session_state.messages[-2]["content"], msg["content"], "bad", correction)
            msg["label"] = "bad"
            msg["show_correction"] = False
            st.toast("✓ Đã ghi nhận!", icon="📝")
            st.rerun()
```

---

## Booking Flow
```python
if st.session_state.booking_mode:
    # (Flow Form Booking giống hệt plan cũ)
    # Ghi nhận Leads...
```
