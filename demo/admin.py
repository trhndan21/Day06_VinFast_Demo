import streamlit as st
import pandas as pd
import sys
import os

# Ensure the demo folder is in path if called from somewhere else
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logger import load_all_entries, get_stats, export_for_training

st.title("🛡️ Admin Dashboard — Flywheel")

stats = get_stats()
all_entries = load_all_entries()

st.subheader("Overview Metrics")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Tổng Tương tác", stats["total"])
col2.metric("👍 Tốt", f"{stats['good']} ({stats['good_rate']}%)")
col3.metric("👎 Xấu/Sai", f"{stats['bad']} ({stats['bad_rate']}%)")
col4.metric("📞 Leads / Blocked", f"{stats['leads']} / {stats['blocked']}")

st.divider()

st.subheader("Export Training Data (JSONL)")
st.markdown("Download dữ liệu đã đánh giá để fine-tune LLM.")

jsonl_str = export_for_training()

st.download_button(
    label="Download Full JSONL",
    data=jsonl_str,
    file_name="training_data.jsonl",
    mime="application/json"
)

style_df = []
for e in all_entries:
    messages = e.get("messages", [])
    if len(messages) >= 3:
        q = messages[1]["content"]
        a = messages[-1]["content"]
        style_df.append({"Query": q, "Answer": a, "Label": e.get("label", "")})

if style_df:
    df = pd.DataFrame(style_df)
    st.dataframe(df)
else:
    st.info("Chưa có tương tác nào.")
