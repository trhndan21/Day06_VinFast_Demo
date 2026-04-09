# Phase 5 — Admin Dashboard (`admin.py`)

> Đọc `CONTEXT.md` trước. File này chỉ mô tả phần Phase 5 đảm nhiệm.

---

## Nhiệm vụ

Xây dựng `admin.py` — Trang Dashboard dành cho quản trị viên (có thể gộp vào multipage của Streamlit):
- Đọc data từ Phase 4 `logger.py` (`load_all_entries`, `get_stats`, `export_for_training`)
- Đọc/ghi Verified Cache vào `cache.json` bằng các hàm từ Phase 3 `search.py`
- Tính toán & hiển thị metrics đơn giản.
- Bảng review các Q&A (nhất là `bad` rating) để admin Verify & đưa vào Cache
- Tính năng export file 1-click Download.

**Lưu ý:** Chỉ dùng UI của `streamlit`, không cần frontend phức tạp.

---

## Skeleton `admin.py`

```python
import streamlit as st
import pandas as pd
from logger import load_all_entries, get_stats, export_for_training
from search import get_all_cache, add_to_cache, delete_cache_entry

st.title("🛡️ Admin Dashboard — Flywheel")

tab1, tab2, tab3 = st.tabs(["📊 Metrics & Log", "🔍 Review (Bad & Low-Conf)", "✅ Verified Cache"])

# --- Lấy dòng data mới nhất ---
stats = get_stats()
all_entries = load_all_entries()
```

---

## Tab 1: Metrics & Log

```python
with tab1:
    st.subheader("Overview Metrics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tổng Tương tác", stats["total"])
    col2.metric("👍 Tốt", f"{stats['good']} ({stats['good_rate']}%)")
    col3.metric("👎 Xấu/Sai", f"{stats['bad']} ({stats['bad_rate']}%)")
    col4.metric("📞 Leads / Blocked", f"{stats['leads']} / {stats['blocked']}")

    st.divider()

    st.subheader("Export Training Data (JSONL)")
    st.markdown("Download dữ liệu đã đánh giá để fine-tune LLM.")
    
    # Text download
    jsonl_str = export_for_training() # lấy tất cả Good/Bad
    
    st.download_button(
        label="Download Full JSONL",
        data=jsonl_str,
        file_name="training_data.jsonl",
        mime="application/json"
    )

    style_df = []
    for e in all_entries:
        if len(e["messages"]) >= 3:
            q = e["messages"][1]["content"]
            a = e["messages"][2]["content"]
            style_df.append({"Query": q, "Answer": a, "Label": e.get("label", "")})
    
    if style_df:
        st.dataframe(pd.DataFrame(style_df), use_container_width=True)
```

---

## Tab 2: Review (Xử lý `bad` labels để ghi vào CSDL RAG / Cache)

```python
with tab2:
    st.subheader("🛠 Cần Review & Sửa chữa")
    st.markdown("Xử lý các dòng bị người dùng đánh giá 👎 (sai, thiếu tự tin).")

    bad_entries = [e for e in all_entries if e.get("label") == "bad"]
    
    if not bad_entries:
        st.success("Tuyệt vời! Không có feedback xấu nào cần xử lý.")
    
    for idx, e in enumerate(bad_entries):
        with st.expander(f"Phản hồi xấu: {e.get('timestamp', 'Unknown')}", expanded=False):
            q = e["messages"][1]["content"]
            a = e["messages"][2]["content"] # Answer cuối cùng (có thể là correction rồi)
            orig_a = e.get("original_answer", "")
            
            st.write(f"**🗣 User hỏi:** {q}")
            st.write(f"**🤖 Cũ AI đáp:** {orig_a}")
            st.write(f"**💡 Người dùng (correction):** {a}")
            
            with st.form(key=f"verify_form_{idx}"):
                final_answer = st.text_area("Câu trả lời chuẩn (Sửa lại trước khi duyệt):", value=a)
                source_url = st.text_input("Link Reference (Nguồn chính thống):")
                submit = st.form_submit_button("✅ Verify & Add to Cache")
                
                if submit:
                    # Gọi hàm add_to_cache từ Phase 3
                    add_to_cache(q, final_answer, source_url)
                    st.success("Đã ghi đè thành công và thêm vào Verified Cache!")
                    st.rerun()
```

---

## Tab 3: Verified Cache

```python
with tab3:
    st.subheader("📚 Verified Answer Cache")
    st.markdown("Cache giúp AI trả lời ngay mà không cần tốn thời gian DDG, đảm bảo độ chính xác (Precision) cao nhất.")
    
    caches = get_all_cache()
    if caches:
        c_df = pd.DataFrame(caches)
        st.dataframe(c_df, use_container_width=True)
        
        st.write("Xóa bỏ Cache:")
        cols = st.columns([3, 1])
        with cols[0]:
            to_delete = st.selectbox("Chọn Cache cần xóa", [c["query"] for c in caches])
        with cols[1]:
            st.write(""); st.write("") # push down
            if st.button("🗑 Xóa"):
                delete_cache_entry(to_delete)
                st.success(f"Đã xóa `{to_delete}` khỏi Cache!")
                st.rerun()
    else:
        st.info("Cache đang trống.")
```

---

## Hướng dẫn Navigation

Nếu bạn dùng chung với `app.py`, bạn có thể tạo 1 file entry point `main.py`:

```python
# main.py
import streamlit as st

st.set_page_config(page_title="VinFast Agent Portal", layout="wide")

pages = {
    "Auto-Agent": [
        st.Page("app.py", title="💬 Chatbot UI"),
        st.Page("admin.py", title="🛡️ Dashboard Admin"),
    ]
}

pg = st.navigation(pages)
pg.run()
```

Và thay vì chạy `streamlit run app.py` thì chạy: `streamlit run main.py`.

---

## Kiểm tra xong Phase 5
- [ ] Chạy `streamlit run admin.py` không gặp lỗi
- [ ] Tab 1 hiển thị Dashboard và tổng kết % `good` / `bad` chính xác. Nút export tải được file JSONL.
- [ ] Tab 2 hiển thị các tin nhắn bị gắn thẻ `bad`. 
- [ ] Điền form trong Tab 2 -> Nhấn Verify -> chuyển sang Tab 3 kiểm tra thấy Cache mới sinh ra.
- [ ] Xóa cache hoạt động tốt. Tiếng Việt không bị lỗi encoding.
```
