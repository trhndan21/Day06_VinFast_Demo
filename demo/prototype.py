# streamlit run prototype.py

import uuid
import time
import json
import os
from dotenv import load_dotenv
import streamlit as st
load_dotenv() 


# ══════════════════════════════════════════════════════════════════════════════
# 1. AI SETUP — OpenAI với fallback mock
# ══════════════════════════════════════════════════════════════════════════════
try:
    from openai import OpenAI as _OpenAIClient
    # _api_key = st.secrets.get("OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    _api_key = os.getenv("OPENAI_API_KEY")
    _client  = _OpenAIClient(api_key=_api_key) if _api_key else None
except Exception:
    _client = None

_USE_LLM   = _client is not None
_LLM_MODEL = "gpt-4o-mini"  # prototype dùng model nhanh, rẻ

# ══════════════════════════════════════════════════════════════════════════════
# 2. SYSTEM PROMPT (embedded knowledge — không cần RAG trong prototype)
# ══════════════════════════════════════════════════════════════════════════════
_SYSTEM_PROMPT = """\
Bạn là VinFast Auto-Agent, trợ lý tư vấn xe VinFast chuyên nghiệp.

DANH MỤC XE VINFAST 2025:
- VF 3:      Hatchback đô thị · 210 km · từ 240 triệu
- VF 5:      SUV mini         · 326 km · từ 458 triệu
- VF 6:      SUV đô thị       · 399 km · từ 675 triệu
- VF 7:      SUV cỡ vừa       · 431 km · từ 850 triệu
- VF 8 Eco:  SUV-D · 471 km · 349 mã lực · từ 1.019 triệu
- VF 8 Plus: SUV-D · 457 km · 402 mã lực · ghế massage · từ 1.199 triệu
- VF 9:      SUV 7 chỗ cao cấp · 438 km · từ 1.499 triệu

CHÍNH SÁCH CHUNG:
- Bảo hành pin:     10 năm / 200.000 km
- Bảo hành thân xe: 5 năm / 100.000 km
- Sạc nhanh DC:     10 % → 70 % trong ~35 phút
- Trả góp:          vay tối đa 80 %, lãi từ 7.5 %/năm, kỳ hạn ≤ 60 tháng
- Trạm sạc nhà:     lắp miễn phí khi mua xe

GUARDRAILS (bắt buộc):
- KHÔNG so sánh hoặc bình luận về hãng xe khác (Toyota, Honda, Kia, BMW, Tesla...)
- KHÔNG trả lời ngoài chủ đề xe VinFast
- Khi không chắc → set suggest_human = true, giải thích lý do

CÁCH CHẤM CONFIDENCE (1-10):
- 9-10: Có chính xác trong danh mục trên
- 7-8:  Tương đối chắc, có thể thay đổi theo khuyến mãi
- 5-6:  Chính sách địa phương hoặc thông tin chưa xác nhận
- 1-4:  Không đủ thông tin, cần chuyên viên

Khi có đủ nhu cầu (mục đích, ngân sách, ưu tiên), gợi ý Top 3 dòng xe phù hợp.

LUÔN trả về JSON đúng format (không thêm text ngoài JSON):
{
  "answer": "câu trả lời markdown",
  "confidence": 8,
  "suggest_human": false,
  "suggest_reason": "",
  "top3": null
}

Khi gợi ý Top 3, điền trường top3:
  "top3": [
    {"model": "VF 8 Eco",  "reason": "tầm pin 471 km phù hợp đường dài", "price_from": 1019},
    {"model": "VF 7",      "reason": "khoang rộng phù hợp gia đình",       "price_from": 850},
    {"model": "VF 8 Plus", "reason": "hiệu suất cao nếu tăng ngân sách",   "price_from": 1199}
  ]
"""

# ══════════════════════════════════════════════════════════════════════════════
# 3. INTAKE — 3 câu hỏi thu thập nhu cầu
# ══════════════════════════════════════════════════════════════════════════════
_INTAKE_Q = [
    (
        "Xin chào! Em là **VinFast Auto-Agent** 🚗\n\n"
        "Để gợi ý dòng xe phù hợp nhất, anh/chị cho em hỏi nhanh 3 câu nhé!\n\n"
        "**1/3 — Anh/chị dùng xe cho mục đích gì?**\n"
        "> *Ví dụ: gia đình · đi làm hàng ngày · kinh doanh · cá nhân*"
    ),
    (
        "**2/3 — Ngân sách anh/chị dự kiến khoảng bao nhiêu?**\n"
        "> *Ví dụ: dưới 600 triệu · 600 triệu – 1 tỷ · trên 1 tỷ*"
    ),
    (
        "**3/3 — Anh/chị ưu tiên điều gì khi chọn xe?**\n"
        "> *Ví dụ: tầm pin xa · hiệu suất mạnh · giá tốt · bảo hành · công nghệ*"
    ),
]

# ══════════════════════════════════════════════════════════════════════════════
# 4. MOCK KNOWLEDGE BASE (fallback khi không có LLM)
# ══════════════════════════════════════════════════════════════════════════════
_VF8_SPECS = """\
Dạ, **VF 8** là mẫu SUV điện cao cấp của VinFast, hiện có **2 phiên bản**:

| Phiên bản | Pin / Tầm hoạt động | Công suất | Mô-men xoắn | Giá từ (Triệu VNĐ) |
|-----------|---------------------|-----------|--------------|---------------------|
| VF 8 Eco  | CATL · 471 km       | 349 mã lực | 500 Nm      | 1.019               |
| VF 8 Plus | CATL · 457 km       | 402 mã lực | 620 Nm      | 1.199               |

*Lưu ý: Giá niêm yết, có thể thay đổi theo chính sách & khuyến mãi.*

Anh/chị quan tâm bản **Eco** hay **Plus** ạ?
"""

_VF8_ECO = """\
**VF 8 Eco** — tối ưu chi phí:

- 🔋 CATL · **471 km** mỗi lần sạc
- ⚡ **349 mã lực**, 500 Nm · 0–100 km/h: **5,9 giây**
- 🛡️ Bảo hành pin **10 năm / 200.000 km**
- 💰 Từ **1.019 triệu** (lăn bánh ~1.035 triệu)

Phù hợp gia đình nội đô và đường dài, chi phí vận hành thấp.
"""

_VF8_PLUS = """\
**VF 8 Plus** — hiệu suất đỉnh cao:

- 🔋 CATL · **457 km** mỗi lần sạc
- ⚡ **402 mã lực**, 620 Nm · 0–100 km/h: **5,5 giây**
- 🪑 Ghế massage · màn hình 15,6" · đèn vây viền
- 🛡️ Bảo hành pin **10 năm / 200.000 km**
- 💰 Từ **1.199 triệu** (lăn bánh ~1.215 triệu)
"""

_VF8_CHARGING = """\
**Sạc điện VF 8:**

- ⚡ Sạc nhanh DC: 10 % → 70 % trong **~35 phút**
- 🔌 Sạc AC tại nhà (11 kW): **~8–9 tiếng**
- 🗺️ **150.000+ điểm sạc** VinFast toàn quốc
- 🏠 **Lắp trạm sạc tại nhà miễn phí** khi mua xe
"""

_VF8_PRICE = """\
**Giá VF 8 (2025):**

| Phiên bản | Niêm yết    | Lăn bánh (ước tính) |
|-----------|-------------|----------------------|
| VF 8 Eco  | 1.019 triệu | ~1.035 triệu         |
| VF 8 Plus | 1.199 triệu | ~1.215 triệu         |

💳 Trả góp: vay **80%** · lãi từ **7.5%/năm** · kỳ hạn **60 tháng**

*Giá lăn bánh phụ thuộc tỉnh/thành — liên hệ showroom để báo giá chính xác.*
"""

_VF8_WARRANTY = """\
**Bảo hành VF 8:**

- 🚗 Thân xe:    **5 năm / 100.000 km**
- 🔋 Pin HV:     **10 năm / 200.000 km**
- ⚙️ Động cơ:   **10 năm / 200.000 km**
- 🛠️ Bảo dưỡng: **miễn phí 3 lần đầu** tại showroom VinFast
"""

_FALLBACK = """\
Em có thể tư vấn về: **giá lăn bánh** · **trả góp** · **sạc điện** · **bảo hành** · **so sánh Eco vs Plus** ✨
"""

_GRD_COMPETITOR = "Em chỉ tư vấn về xe VinFast ạ 😊 Anh/chị muốn tìm hiểu dòng xe nào không?"
_GRD_OFFTOPIC   = "Em là trợ lý tư vấn xe VinFast, chỉ hỗ trợ câu hỏi liên quan đến xe ạ 😊"

_COMPETITORS = ["toyota", "honda", "kia", "bmw", "mercedes", "hyundai", "mazda", "ford", "tesla", "mitsubishi"]
_OFFTOPIC    = ["thời tiết", "nấu ăn", "chính trị", "bóng đá", "crypto", "bitcoin"]

_VN_DAYS = {
    "Monday": "Thứ Hai", "Tuesday": "Thứ Ba", "Wednesday": "Thứ Tư",
    "Thursday": "Thứ Năm", "Friday": "Thứ Sáu", "Saturday": "Thứ Bảy",
    "Sunday": "Chủ Nhật",
}

# ══════════════════════════════════════════════════════════════════════════════
# 5. CAR CATALOG — dùng cho Top 3 smart mock
# ══════════════════════════════════════════════════════════════════════════════
_CAR_CATALOG = [
    {"model": "VF 3",      "price": 240,  "range_km": 210, "budget_tier": 1,
     "tags": ["đô thị", "cá nhân", "tiết kiệm", "ngắn"]},
    {"model": "VF 5",      "price": 458,  "range_km": 326, "budget_tier": 1,
     "tags": ["gia đình nhỏ", "đô thị", "tiết kiệm"]},
    {"model": "VF 6",      "price": 675,  "range_km": 399, "budget_tier": 2,
     "tags": ["gia đình", "đô thị", "kinh doanh", "giá tốt"]},
    {"model": "VF 7",      "price": 850,  "range_km": 431, "budget_tier": 2,
     "tags": ["gia đình", "hiệu suất", "công nghệ"]},
    {"model": "VF 8 Eco",  "price": 1019, "range_km": 471, "budget_tier": 3,
     "tags": ["tầm pin dài", "gia đình", "đường dài", "hiệu suất"]},
    {"model": "VF 8 Plus", "price": 1199, "range_km": 457, "budget_tier": 3,
     "tags": ["hiệu suất cao", "công nghệ", "sang trọng", "thể thao"]},
    {"model": "VF 9",      "price": 1499, "range_km": 438, "budget_tier": 3,
     "tags": ["gia đình lớn", "7 chỗ", "cao cấp", "rộng rãi"]},
]


def _top3_smart_mock(intake_answers: list) -> list:
    """Xếp hạng Top 3 dựa trên keyword — dùng khi không có LLM."""
    text = " ".join(intake_answers).lower()

    # Detect budget tier
    if any(k in text for k in ["dưới", "600", "thấp", "ít tiền", "rẻ"]):
        budget_tier = 1
    elif any(k in text for k in ["trên 1", "1 tỷ", "1.5", "cao"]):
        budget_tier = 3
    else:
        budget_tier = 2

    # Detect preference tags
    pref = []
    if any(k in text for k in ["gia đình", "con", "vợ", "chồng", "7 chỗ", "rộng"]):
        pref.append("gia đình")
    if any(k in text for k in ["pin", "tầm", "xa", "đường dài"]):
        pref.append("tầm pin dài")
    if any(k in text for k in ["mạnh", "nhanh", "thể thao", "hiệu suất"]):
        pref.append("hiệu suất cao")
    if any(k in text for k in ["kinh doanh", "dịch vụ"]):
        pref.append("kinh doanh")
    if any(k in text for k in ["tiết kiệm", "rẻ", "giá tốt"]):
        pref.append("giá tốt")

    scored = []
    for car in _CAR_CATALOG:
        score = 3 if car["budget_tier"] == budget_tier else (1 if car["budget_tier"] == budget_tier - 1 else -2)
        for tag in pref:
            if any(tag in t for t in car["tags"]):
                score += 2
        scored.append((score, car))

    scored.sort(key=lambda x: -x[0])
    results = []
    for _, car in scored[:3]:
        matched = [t for t in car["tags"] if any(p in t for p in pref)]
        reason  = matched[0] if matched else f"tầm hoạt động {car['range_km']} km"
        results.append({"model": car["model"], "reason": reason, "price_from": car["price"]})
    return results


# ══════════════════════════════════════════════════════════════════════════════
# 6. ENGINE — LLM call + mock fallback
# ══════════════════════════════════════════════════════════════════════════════

def _guardrail_fast(query: str) -> str | None:
    """Keyword guardrail — không tốn token LLM."""
    q = query.lower()
    if any(kw in q for kw in _COMPETITORS):
        return _GRD_COMPETITOR
    if any(kw in q for kw in _OFFTOPIC):
        return _GRD_OFFTOPIC
    return None


def _mock_respond(query: str) -> dict:
    """Mock engine rule-based — fallback."""
    q = query.lower()
    if any(kw in q for kw in ["bảo hành", "sạc", "trạm"]) and "thứ 3" in q:
        return {"answer": "Chính sách sạc bên thứ 3 phụ thuộc hợp đồng riêng.",
                "confidence": 5, "suggest_human": True,
                "suggest_reason": "Cần xác nhận từ đại lý chính hãng.", "top3": None}
    if "eco" in q:
        return {"answer": _VF8_ECO,       "confidence": 9, "suggest_human": False, "suggest_reason": "", "top3": None}
    if "plus" in q:
        return {"answer": _VF8_PLUS,      "confidence": 9, "suggest_human": False, "suggest_reason": "", "top3": None}
    if any(kw in q for kw in ["sạc", "trạm sạc"]):
        return {"answer": _VF8_CHARGING,  "confidence": 9, "suggest_human": False, "suggest_reason": "", "top3": None}
    if any(kw in q for kw in ["giá", "bao nhiêu", "tiền", "lăn bánh", "trả góp"]):
        return {"answer": _VF8_PRICE,     "confidence": 8, "suggest_human": False, "suggest_reason": "", "top3": None}
    if any(kw in q for kw in ["bảo hành", "warranty", "bảo trì"]):
        return {"answer": _VF8_WARRANTY,  "confidence": 9, "suggest_human": False, "suggest_reason": "", "top3": None}
    if any(kw in q for kw in ["vf8", "vf 8", "tư vấn", "giới thiệu"]):
        return {"answer": _VF8_SPECS,     "confidence": 9, "suggest_human": False, "suggest_reason": "", "top3": None}
    return {"answer": _FALLBACK,          "confidence": 6, "suggest_human": False, "suggest_reason": "", "top3": None}


def _llm_call(messages: list) -> dict:
    """Gọi OpenAI và parse JSON trả về."""
    try:
        resp = _client.chat.completions.create(  # type: ignore[union-attr]
            model=_LLM_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=800,
        )
        data = json.loads(resp.choices[0].message.content)
        return {
            "answer":         data.get("answer", ""),
            "confidence":     int(data.get("confidence", 7)),
            "suggest_human":  bool(data.get("suggest_human", False)),
            "suggest_reason": data.get("suggest_reason", ""),
            "top3":           data.get("top3", None),
        }
    except Exception as e:
        return {"answer": f"Lỗi kết nối AI ({type(e).__name__}), thử lại sau nhé.",
                "confidence": 1, "suggest_human": True,
                "suggest_reason": "Lỗi kỹ thuật", "top3": None}


def _llm_respond(query: str, intake_context: str = "") -> dict:
    messages: list = [{"role": "system", "content": _SYSTEM_PROMPT}]
    if intake_context:
        messages += [
            {"role": "user",      "content": f"[Thông tin nhu cầu]\n{intake_context}"},
            {"role": "assistant", "content": '{"answer":"Dạ em đã ghi nhận.","confidence":10,"suggest_human":false,"suggest_reason":"","top3":null}'},
        ]
    messages.append({"role": "user", "content": query})
    return _llm_call(messages)


def respond(query: str, intake_context: str = "") -> dict:
    block = _guardrail_fast(query)
    if block:
        return {"block_message": block, "confidence": 10,
                "suggest_human": False, "suggest_reason": "", "top3": None}
    return _llm_respond(query, intake_context) if _USE_LLM else _mock_respond(query)


def generate_top3(intake_answers: list) -> dict:
    """Sinh Top 3 ngay sau khi intake xong."""
    if _USE_LLM:
        summary = (f"Mục đích: {intake_answers[0]}\n"
                   f"Ngân sách: {intake_answers[1]}\n"
                   f"Ưu tiên: {intake_answers[2]}")
        result = _llm_respond(
            "Dựa trên thông tin nhu cầu trên, gợi ý Top 3 dòng xe VinFast phù hợp nhất.",
            intake_context=summary,
        )
        if result.get("top3"):
            return result

    # Fallback smart mock
    top3 = _top3_smart_mock(intake_answers)
    return {"answer": "Dựa trên thông tin anh/chị chia sẻ, đây là **Top 3 dòng xe VinFast** em gợi ý:",
            "confidence": 8, "suggest_human": False, "suggest_reason": "", "top3": top3}


# ══════════════════════════════════════════════════════════════════════════════
# 7. SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="VinFast Auto-Agent", page_icon="🚗", layout="centered")

_DEFAULTS: dict = {
    "messages":          [],
    "turn_count":        0,
    "intake_step":       0,       # 0 = chưa bắt đầu; 1,2 = đang hỏi; 3 = xong
    "intake_answers":    [],
    "intake_summary":    "",
    "show_booking_form": False,
    "booking_done":      False,
    "feedback":          {},      # {msg_id: "up" | "down"}
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ══════════════════════════════════════════════════════════════════════════════
# 8. UI HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def render_confidence(conf: int) -> None:
    if conf >= 8:
        color, label = "#27ae60", "Độ tin cậy cao"
    elif conf >= 6:
        color, label = "#f39c12", "Cần xác nhận thêm"
    else:
        color, label = "#e74c3c", "Cần chuyên viên"
    st.markdown(
        f'<span style="background:{color};color:white;padding:2px 9px;'
        f'border-radius:10px;font-size:0.75em">🎯 {conf}/10 · {label}</span>',
        unsafe_allow_html=True,
    )


def render_top3_card(top3: list) -> None:
    st.markdown("---")
    medals = ["🥇", "🥈", "🥉"]
    cols   = st.columns(len(top3))
    for i, (col, car) in enumerate(zip(cols, top3)):
        with col:
            with st.container(border=True):
                st.markdown(f"**{medals[i]} {car['model']}**")
                st.caption(car["reason"])
                st.markdown(f"💰 Từ **{car['price_from']:,} triệu**")
    st.markdown("---")


def render_low_confidence_card(reason: str, msg_id: str) -> None:
    with st.container(border=True):
        st.warning(f"⚠️ **Em chưa chắc vì:** {reason}")
        st.write("Anh/chị có muốn gặp tư vấn viên VinFast không?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📞 Gặp tư vấn viên", key=f"consult_{msg_id}"):
                st.session_state.show_booking_form = True
                st.rerun()
        with c2:
            st.button("Tiếp tục chat", key=f"skip_{msg_id}")


def render_feedback_buttons(msg_id: str) -> None:
    current = st.session_state.feedback.get(msg_id)
    if current:
        st.caption("✅ Cảm ơn!" if current == "up" else "📝 Đã ghi nhận lỗi")
        return
    c1, c2, _ = st.columns([1, 1, 5])
    with c1:
        if st.button("👍", key=f"up_{msg_id}", help="Hữu ích"):
            st.session_state.feedback[msg_id] = "up"
            st.rerun()
    with c2:
        if st.button("👎", key=f"dn_{msg_id}", help="Thông tin sai"):
            st.session_state.feedback[msg_id] = "down"
            st.rerun()


def _success_md(name: str, car: str, date, time_slot: str, location: str) -> str:
    day_str = f"{_VN_DAYS.get(date.strftime('%A'), '')} ({date.strftime('%d/%m/%Y')})"
    return (
        "### ✅ Xác nhận đặt lịch thành công\n\n"
        "🎉 **Đặt lịch lái thử thành công!**\n\n"
        f"📅 **Thời gian:** {time_slot}, {day_str}  \n"
        f"📍 **Showroom:** VinFast {location}  \n"
        f"🚗 **Dòng xe:** {car}  \n\n"
        f"📞 *Nhân viên sẽ liên hệ **{name}** trước giờ lái thử để xác nhận.*"
    )

# ══════════════════════════════════════════════════════════════════════════════
# 9. HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.title("🚗 VinFast Auto-Agent")
mode_label = "🤖 AI Mode (OpenAI)" if _USE_LLM else "🎭 Demo Mode (Mock)"
st.caption(f"{mode_label} · Trợ lý tư vấn xe VinFast")
st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# 10. KHỞI TẠO INTAKE — hiện câu hỏi đầu khi chat trống
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.messages and st.session_state.intake_step == 0:
    st.session_state.messages.append({
        "id": str(uuid.uuid4()), "role": "assistant",
        "content": _INTAKE_Q[0], "confidence": 10, "is_intake": True,
    })

# ══════════════════════════════════════════════════════════════════════════════
# 11. RENDER LỊCH SỬ CHAT
# ══════════════════════════════════════════════════════════════════════════════
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        if msg.get("is_intake") or msg.get("blocked") or msg.get("is_booking_success"):
            continue

        # Confidence badge
        if msg["role"] == "assistant" and "confidence" in msg:
            render_confidence(msg["confidence"])

        # Top 3 card
        if msg.get("top3"):
            render_top3_card(msg["top3"])

        # Low-confidence card
        if msg.get("suggest_reason"):
            render_low_confidence_card(msg["suggest_reason"], msg["id"])

        # Feedback buttons
        if msg["role"] == "assistant":
            render_feedback_buttons(msg["id"])

# ══════════════════════════════════════════════════════════════════════════════
# 12. BOOKING FORM
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.show_booking_form and not st.session_state.booking_done:
    with st.chat_message("assistant"):
        st.markdown("Dạ được! Anh/chị vui lòng điền thông tin để đặt lịch lái thử:")
        with st.form("booking_form"):
            name     = st.text_input("1. Tên của anh/chị:")
            phone    = st.text_input("2. Số điện thoại:")
            car      = st.selectbox("3. Dòng xe muốn lái thử:",
                                    ["VF 8 Eco", "VF 8 Plus", "VF 9", "VF 7", "VF 6", "VF 5"])
            time_opt = st.selectbox("4. Giờ lái thử:",
                                    ["9:00 – 10:30", "10:30 – 12:00", "13:00 – 14:30", "14:30 – 16:00"])
            location = st.selectbox("5. Showroom gần nhất:",
                                    ["Hà Nội – Giải Phóng", "TP.HCM – Phạm Văn Đồng",
                                     "Đà Nẵng", "Cần Thơ", "Hải Phòng", "Khác"])
            date     = st.date_input("6. Ngày lái thử:")
            c1, c2   = st.columns(2)
            with c1:
                submitted = st.form_submit_button("Gửi thông tin", type="primary", use_container_width=True)
            with c2:
                cancelled = st.form_submit_button("Hủy", use_container_width=True)

        if submitted:
            if not name.strip() or not phone.strip():
                st.error("Vui lòng nhập đầy đủ họ tên và số điện thoại.")
            else:
                st.session_state.messages.append({
                    "id": str(uuid.uuid4()), "role": "assistant",
                    "content": _success_md(name, car, date, time_opt, location),
                    "is_booking_success": True,
                })
                st.session_state.show_booking_form = False
                st.session_state.booking_done      = True
                st.rerun()
        if cancelled:
            st.session_state.show_booking_form = False
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# 13. CTA đặt lịch / Done reset
# ══════════════════════════════════════════════════════════════════════════════
elif (st.session_state.intake_step >= 3
      and st.session_state.turn_count >= 2
      and not st.session_state.booking_done
      and not st.session_state.show_booking_form):
    _, col_btn = st.columns([3, 2])
    with col_btn:
        if st.button("🚗 Đặt lịch lái thử", type="primary", use_container_width=True):
            st.session_state.show_booking_form = True
            st.rerun()

elif st.session_state.booking_done:
    _, col_btn = st.columns([3, 2])
    with col_btn:
        if st.button("Cảm ơn, mình đã rõ rồi ✅", use_container_width=True):
            for k, v in _DEFAULTS.items():
                st.session_state[k] = v
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# 14. CHAT INPUT
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.show_booking_form:
    intake_done = st.session_state.intake_step >= 3

    if prompt := st.chat_input("Trả lời hoặc hỏi về xe VinFast..."):
        user_id = str(uuid.uuid4())
        st.session_state.messages.append({"role": "user", "content": prompt, "id": user_id})
        with st.chat_message("user"):
            st.markdown(prompt)

        # ── INTAKE PHASE ──────────────────────────────────────────────────────
        if not intake_done:
            st.session_state.intake_answers.append(prompt)
            st.session_state.intake_step += 1
            next_step = st.session_state.intake_step

            with st.chat_message("assistant"):
                if next_step < 3:
                    q_text = _INTAKE_Q[next_step]
                    st.markdown(q_text)
                    st.session_state.messages.append({
                        "id": str(uuid.uuid4()), "role": "assistant",
                        "content": q_text, "confidence": 10, "is_intake": True,
                    })
                else:
                    # Intake xong → sinh Top 3
                    answers = st.session_state.intake_answers
                    st.session_state.intake_summary = (
                        f"Mục đích: {answers[0]}\n"
                        f"Ngân sách: {answers[1]}\n"
                        f"Ưu tiên: {answers[2]}"
                    )
                    with st.spinner("Đang phân tích và gợi ý dòng xe..."):
                        time.sleep(0.4)
                        result = generate_top3(answers)

                    answer = result.get("answer", "Đây là Top 3 gợi ý của em:")
                    conf   = result.get("confidence", 8)
                    top3   = result.get("top3", [])

                    st.markdown(answer)
                    render_confidence(conf)
                    if top3:
                        render_top3_card(top3)
                    st.markdown(
                        "Anh/chị muốn tìm hiểu thêm dòng nào, "
                        "hoặc hỏi về giá · sạc điện · bảo hành · trả góp — em sẵn sàng tư vấn tiếp! 😊"
                    )

                    msg_id = str(uuid.uuid4())
                    st.session_state.messages.append({
                        "id": msg_id, "role": "assistant",
                        "content": answer, "confidence": conf, "top3": top3,
                    })
                    render_feedback_buttons(msg_id)

        # ── REGULAR CHAT PHASE ────────────────────────────────────────────────
        else:
            with st.chat_message("assistant"):
                with st.spinner("Đang tìm kiếm thông tin..."):
                    time.sleep(0.4)
                    result = respond(prompt, st.session_state.intake_summary)

                msg_id       = str(uuid.uuid4())
                response_msg = {"id": msg_id, "role": "assistant"}

                if result.get("block_message"):
                    response_msg["content"] = result["block_message"]
                    response_msg["blocked"]  = True
                    st.markdown(result["block_message"])
                else:
                    answer = result.get("answer", "")
                    conf   = result.get("confidence", 7)
                    top3   = result.get("top3")

                    response_msg.update({"content": answer, "confidence": conf})
                    if top3:
                        response_msg["top3"] = top3

                    st.markdown(answer)
                    render_confidence(conf)
                    if top3:
                        render_top3_card(top3)
                    if result.get("suggest_human"):
                        response_msg["suggest_reason"] = result.get("suggest_reason", "")
                        render_low_confidence_card(response_msg["suggest_reason"], msg_id)

                    render_feedback_buttons(msg_id)
                    st.session_state.turn_count += 1

                st.session_state.messages.append(response_msg)

        st.rerun()
