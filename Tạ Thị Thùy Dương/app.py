import streamlit as st
import uuid

from duong.constants import CONFIDENCE_THRESHOLD

# --- Import thật khi Phase 2 & 4 sẵn; dùng stub để chạy thử độc lập ---
try:
    from engine import agent_app
except ImportError:
    from duong.engine_stub import agent_app

try:
    from logger import append_entry
except ImportError:
    from duong.logger_stub import append_entry

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="VinFast Auto-Agent",
    page_icon="🚗",
    layout="centered",
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "booking_mode" not in st.session_state:
    st.session_state.booking_mode = False


# ---------------------------------------------------------------------------
# Helper: Suggest card (hiện khi AI không chắc)
# ---------------------------------------------------------------------------
def render_suggest_card(reason: str, msg_id: str) -> None:
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


# ---------------------------------------------------------------------------
# Helper: Feedback buttons (👍 / 👎)
# ---------------------------------------------------------------------------
def render_feedback(msg: dict) -> None:
    # Tìm câu hỏi của user ngay trước message này
    messages = st.session_state.messages
    idx = next(
        (i for i, m in enumerate(messages) if m.get("id") == msg.get("id")),
        None,
    )
    question = ""
    if idx is not None and idx > 0:
        question = messages[idx - 1].get("content", "")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("👍 Tốt", key=f"good_{msg['id']}"):
            append_entry(question, msg["content"], "good")
            msg["label"] = "good"
            st.toast("Cảm ơn phản hồi!", icon="✅")
    with col2:
        if st.button("👎 Sai", key=f"bad_{msg['id']}"):
            msg["show_correction"] = True
            st.rerun()

    if msg.get("show_correction"):
        correction = st.text_input(
            "Câu đúng là gì? (tuỳ chọn)", key=f"corr_{msg['id']}"
        )
        if st.button("Gửi báo lỗi", key=f"submit_{msg['id']}"):
            append_entry(question, msg["content"], "bad", correction)
            msg["label"] = "bad"
            msg["show_correction"] = False
            st.toast("Đã ghi nhận!", icon="📝")
            st.rerun()


# ---------------------------------------------------------------------------
# UI: Header
# ---------------------------------------------------------------------------
st.title("🚗 VinFast Auto-Agent")
st.caption("Trợ lý tư vấn xe độc lập (Giả lập) • Được hỗ trợ bởi LangGraph")
st.divider()

# ---------------------------------------------------------------------------
# Booking form (ưu tiên hiện trước chat khi đang ở booking_mode)
# ---------------------------------------------------------------------------
if st.session_state.booking_mode:
    st.subheader("📅 Đặt lịch lái thử")
    with st.form("booking_form"):
        name = st.text_input("Họ tên")
        phone = st.text_input("Số điện thoại")
        date = st.date_input("Ngày lái thử mong muốn")
        location = st.selectbox(
            "Showroom",
            ["TP.HCM", "Hà Nội", "Đà Nẵng", "Cần Thơ", "Hải Phòng", "Khác"],
        )
        submitted = st.form_submit_button("✅ Xác nhận đặt lịch")

    if submitted:
        if not name.strip() or not phone.strip():
            st.error("Vui lòng nhập đầy đủ họ tên và số điện thoại.")
        else:
            lead_content = f"Lead: {name} | {phone} | {date} | {location}"
            append_entry("[BOOKING]", lead_content, "lead")
            st.success(
                "Đã ghi nhận thông tin! CSKH VinFast sẽ liên hệ xác nhận lịch lái thử sớm nhất."
            )
            st.session_state.booking_mode = False
            st.rerun()

    if st.button("← Quay lại chat"):
        st.session_state.booking_mode = False
        st.rerun()

    st.stop()  # không render phần chat khi đang ở booking_mode

# ---------------------------------------------------------------------------
# Render lịch sử chat
# ---------------------------------------------------------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Guardrail block — không cần feedback
        if msg.get("blocked"):
            continue

        # Suggest card nếu AI không chắc
        if msg.get("suggest_reason"):
            render_suggest_card(msg["suggest_reason"], msg["id"])

        # Feedback chỉ cho assistant và chưa được label
        if msg["role"] == "assistant" and not msg.get("label"):
            render_feedback(msg)

# ---------------------------------------------------------------------------
# Xử lý user input
# ---------------------------------------------------------------------------
if prompt := st.chat_input("Hỏi về xe VinFast..."):
    user_id = str(uuid.uuid4())
    st.session_state.messages.append(
        {"role": "user", "content": prompt, "id": user_id}
    )
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Đang tìm kiếm thông tin..."):
            final_state = agent_app.invoke({"input": prompt})

        msg_id = str(uuid.uuid4())
        response_msg: dict = {"id": msg_id, "role": "assistant"}

        if final_state.get("block_message"):
            # --- Guardrail block ---
            response_msg["content"] = final_state["block_message"]
            response_msg["blocked"] = True
            st.markdown(final_state["block_message"])
            append_entry(prompt, final_state["block_message"], "blocked")
        else:
            # --- Câu trả lời thành công (cache hit hoặc reasoning) ---
            answer = final_state.get("answer", "")
            response_msg["content"] = answer
            response_msg["meta"] = {
                "confidence": final_state.get("confidence", 0),
                "source_url": final_state.get("source_url", ""),
            }
            st.markdown(answer)

            # Source URL nếu có
            source_url = final_state.get("source_url", "")
            if source_url:
                st.caption(f"Nguồn: {source_url}")

            # Suggest card nếu AI không chắc
            if final_state.get("suggest_human"):
                response_msg["suggest_reason"] = final_state.get("suggest_reason", "")
                render_suggest_card(response_msg["suggest_reason"], msg_id)

            render_feedback(response_msg)

    st.session_state.messages.append(response_msg)
    st.rerun()
