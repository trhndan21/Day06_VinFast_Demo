import streamlit as st
import time
import uuid
import sys
import os
from engine import agent_app, summarize_memory
from logger import append_entry

# Ensure the demo folder is in path if called from somewhere else
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(page_title="VinFast Auto-Agent", page_icon="🚗", layout="wide")

if "chat_sessions" not in st.session_state:
    default_id = str(uuid.uuid4())
    st.session_state.chat_sessions = {
        default_id: {
            "name": "Cuộc trò chuyện mới",
            "messages": [],
            "memory_cache": []
        }
    }
    st.session_state.current_session_id = default_id

if "booking_mode" not in st.session_state:
    st.session_state.booking_mode = False

curr_session = st.session_state.chat_sessions[st.session_state.current_session_id]

# Sidebar
with st.sidebar:
    st.title("🗂️ Lịch sử Hội thoại")
    if st.button("➕ Tạo Chat Mới", use_container_width=True):
        new_id = str(uuid.uuid4())
        st.session_state.chat_sessions[new_id] = {
            "name": f"Hội thoại mới",
            "messages": [],
            "memory_cache": []
        }
        st.session_state.current_session_id = new_id
        st.rerun()
    
    st.divider()
    for s_id, s_data in reversed(list(st.session_state.chat_sessions.items())):
        prefix = "✅ " if s_id == st.session_state.current_session_id else "💬 "
        if st.button(f"{prefix}{s_data['name']}", key=f"switch_{s_id}", use_container_width=True):
            st.session_state.current_session_id = s_id
            st.rerun()

def render_suggest_card(reason, msg_id):
    with st.container(border=True):
        st.warning("Anh/chị có muốn em kết nối với tư vấn viên VinFast để được hỗ trợ chuyên sâu hơn thông tin này không?")
        
        cols = st.columns([1, 3])
        with cols[0]:
            if st.button("📞 Gọi tư vấn viên", key=f"call_{msg_id}", use_container_width=True):
                st.session_state.booking_mode = True
                st.rerun()

def render_feedback(msg):
    c_sess = st.session_state.chat_sessions[st.session_state.current_session_id]
    col1, col2 = st.columns([1, 1])
    
    user_prompt = msg.get("meta", {}).get("user_prompt", "Unknown User Prompt")
    
    with col1:
        if st.button("👍 Tốt", key=f"good_{msg['id']}"):
            append_entry(user_prompt, msg["content"], "good")
            msg["label"] = "good"
            st.toast("✓ Cảm ơn phản hồi!", icon="✅")
            st.rerun()
    with col2:
        if st.button("👎 Sai", key=f"bad_{msg['id']}"):
            append_entry(user_prompt, msg["content"], "bad")
            msg["label"] = "bad"
            st.toast("✓ Đã ghi nhận đánh giá!", icon="📝")
            st.rerun()



st.title("🚗 VinFast Auto-Agent")
st.caption("Trợ lý tư vấn xe độc lập (Giả lập) • Được hỗ trợ bởi LangGraph")
st.divider()

for msg in curr_session["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("meta") and msg["meta"].get("confidence", 10) < 7:
            if msg.get("suggest_reason"):
                render_suggest_card(msg["suggest_reason"], msg["id"])
        
        if msg["role"] == "assistant" and not msg.get("label") and not msg.get("blocked"):
            render_feedback(msg)

if st.session_state.booking_mode:
    st.subheader("Để lại thông tin để chuyên viên VinFast hỗ trợ")
    with st.form("booking_form"):
        name = st.text_input("Họ và tên")
        phone = st.text_input("Số điện thoại")
        date = st.date_input("Ngày dự kiến lái thử/tư vấn")
        submitted = st.form_submit_button("Gửi thông tin")
        if submitted:
            append_entry(
                question="[BOOKING]", 
                answer=f"Lead: {name} | {phone} | {date}", 
                label="lead"
            )
            st.success("Cảm ơn anh/chị. Chuyên viên sẽ liên hệ lại sớm nhất!")
            st.session_state.booking_mode = False
            st.rerun()

if not st.session_state.booking_mode:
    if prompt := st.chat_input("Hỏi về xe VinFast..."):
        # Rename session nicely if it's the first message
        if len(curr_session["messages"]) == 0:
            curr_session["name"] = prompt[:20] + ("..." if len(prompt) > 20 else "")

        curr_session["messages"].append({"role": "user", "content": prompt, "id": str(uuid.uuid4())})
        st.rerun()

    if len(curr_session["messages"]) > 0 and curr_session["messages"][-1]["role"] == "user":
        prompt = curr_session["messages"][-1]["content"]

        with st.chat_message("assistant"):
            with st.spinner("Đang tìm kiếm thông tin..."):
                final_state = agent_app.invoke({
                    "input": prompt,
                    "chat_history": curr_session["memory_cache"]
                })
                
                msg_id = str(uuid.uuid4())
                assistant_msg = {
                    "id": msg_id,
                    "role": "assistant"
                }

                if final_state.get("block_message"):
                    assistant_msg["content"] = final_state["block_message"]
                    assistant_msg["blocked"] = True
                    append_entry(prompt, final_state["block_message"], "blocked")
                    st.markdown(final_state["block_message"])
                else:
                    assistant_msg["content"] = final_state["answer"]
                    assistant_msg["meta"] = {
                        "user_prompt": prompt,
                        "confidence": final_state.get("confidence", 0),
                        "source_url": final_state.get("source_url", "")
                    }
                    
                    st.markdown(final_state["answer"])
                    
                    if final_state.get("suggest_human"):
                        assistant_msg["suggest_reason"] = final_state["suggest_reason"]
                        render_suggest_card(final_state["suggest_reason"], msg_id)
                    
                    render_feedback(assistant_msg)

        curr_session["messages"].append(assistant_msg)
        
        if "answer" in final_state and isinstance(final_state["answer"], str) and not final_state.get("block_message"):
            turn = f"User: {prompt}\nAI: {final_state['answer']}"
            curr_session["memory_cache"].append(turn)

            if len(curr_session["memory_cache"]) >= 3:
                with st.spinner("Đang nén bộ nhớ để tối ưu tốc độ..."):
                    summary = summarize_memory(curr_session["memory_cache"])
                    curr_session["memory_cache"] = [f"{summary}"]
        
        st.rerun()
