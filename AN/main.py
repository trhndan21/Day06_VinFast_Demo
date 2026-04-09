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
