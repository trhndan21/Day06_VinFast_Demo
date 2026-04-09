import json
import os
import re
import requests
import streamlit as st
from datetime import datetime, timezone
from constants import STR_SEARCH_ENGINE_URL

def _normalize(q: str) -> str:
    return re.sub(r"[?!.,]+$", "", q.lower().strip())

def get_tavily_key():
    try:
        return st.secrets["TAVILY_API_KEY"]
    except Exception:
        return os.environ.get("TAVILY_API_KEY", "")

def search_tavily(query: str) -> dict:
    try:
        headers = {"Content-Type": "application/json"}
        payload = {
            "api_key": get_tavily_key(),
            "query": f"VinFast {query}",
            "search_depth": "basic",
            "include_answer": False,
            "max_results": 3
        }
        resp = requests.post(STR_SEARCH_ENGINE_URL, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return _parse_tavily(data)
    except Exception as e:
        print(f"Error in search_tavily: {e}")
        return {"snippets": [], "urls": []}

def _parse_tavily(data: dict) -> dict:
    snippets = []
    urls = []

    for result in data.get("results", []):
        content = result.get("content", "")
        url = result.get("url", "")
        if content and url:
            snippets.append(content)
            urls.append(url)

    return {
        "snippets": snippets[:3],
        "urls": urls[:3]
    }


