import json
import os
import re
import requests
from datetime import datetime, timezone

# Import từ file constants.py (yêu cầu phải có file này cùng thư mục)
from constants import CACHE_FILE, DDG_API

# --- CẤU HÌNH ---
OFFLINE_MODE = False   # Set True khi không có internet để chạy demo

MOCK_DATA = {
    "vf 8 giá bao nhiêu": {
        "snippets": ["VF 8 Eco có giá 1.057 tỷ đồng, bản Plus 1.234 tỷ đồng."],
        "urls"    : ["https://vinfastautovn.com/vf8"]
    },
    "vf 3 giá bao nhiêu": {
        "snippets": ["VF 3 có giá khởi điểm 240 triệu đồng."],
        "urls"    : ["https://vinfastautovn.com/vf3"]
    },
}

# --- HÀM HỖ TRỢ ---
def _normalize(q: str) -> str:
    """lowercase, trim, bỏ dấu câu cuối"""
    return re.sub(r"[?!.,]+$", "", q.lower().strip())

def _parse_ddg(data: dict) -> dict:
    snippets = []
    urls     = []

    # Source 1: Abstract (Wikipedia / official answer)
    if data.get("AbstractText"):
        snippets.append(data["AbstractText"])
        urls.append(data.get("AbstractURL", ""))

    # Source 2: Related Topics
    for topic in data.get("RelatedTopics", [])[:4]:
        text = topic.get("Text", "")
        url  = topic.get("FirstURL", "")
        if text and url:
            snippets.append(text)
            urls.append(url)
        if len(snippets) >= 3:
            break

    # Source 3: Direct Results
    for result in data.get("Results", [])[:2]:
        if result.get("Text"):
            snippets.append(result["Text"])
            urls.append(result.get("FirstURL", ""))
        if len(snippets) >= 3:
            break

    return {
        "snippets": snippets[:3],
        "urls"    : urls[:3]
    }

# --- HÀM CHÍNH ---
def check_cache(query: str) -> dict:
    norm = _normalize(query)
    if not os.path.exists(CACHE_FILE):
        return {"hit": False, "entry": None}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        for entry in cache:
            if entry.get("query") == norm:
                return {"hit": True, "entry": entry}
    except Exception:
        pass
    return {"hit": False, "entry": None}

def search_ddg(query: str) -> dict:
    if OFFLINE_MODE:
        norm = _normalize(query)
        return MOCK_DATA.get(norm, {"snippets": [], "urls": []})
        
    try:
        params = {
            "q"             : f"vinfast {query}",
            "format"        : "json",
            "no_html"       : "1",
            "skip_disambig" : "1",
        }
        resp = requests.get(DDG_API, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return _parse_ddg(data)
    except Exception:
        return {"snippets": [], "urls": []}

def add_to_cache(query: str, answer: str, source_url: str = "") -> None:
    norm = _normalize(query)
    cache = []
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = []

    # Update nếu đã tồn tại, không tạo duplicate
    existing = next((i for i, e in enumerate(cache) if e["query"] == norm), None)
    entry = {
        "query"     : norm,
        "answer"    : answer,
        "source_url": source_url,
        "added_at"  : datetime.now(timezone.utc).isoformat()
    }
    
    if existing is not None:
        cache[existing] = entry
    else:
        cache.append(entry)

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def get_all_cache() -> list:
    if not os.path.exists(CACHE_FILE):
        return []
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def delete_cache_entry(query_norm: str) -> None:
    cache = get_all_cache()
    cache = [e for e in cache if e["query"] != query_norm]
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# --- KIỂM TRA (CHỈ CHẠY KHI GỌI TRỰC TIẾP FILE NÀY) ---
if __name__ == "__main__":
    print("-> Bắt đầu chạy test file search.py...")
    
    # 1. Normalize
    assert _normalize("VF 8 giá bao nhiêu???") == "vf 8 giá bao nhiêu", "Lỗi hàm _normalize"

    # 2. Add to cache
    add_to_cache("VF 8 giá bao nhiêu", "VF 8 Eco 1.057 tỷ...", "https://vinfastautovn.com/vf8")

    # 3. Cache hit
    result2 = check_cache("VF 8 giá bao nhiêu")
    assert result2["hit"] == True, "Lỗi đọc/ghi Cache"
    assert "answer" in result2["entry"], "Lỗi định dạng cấu trúc Cache entry"

    # 4. DDG search (Cần internet nếu OFFLINE_MODE = False)
    data = search_ddg("vf 8")
    assert isinstance(data["snippets"], list), "Lỗi kiểu dữ liệu trả về của snippets"
    assert isinstance(data["urls"], list), "Lỗi kiểu dữ liệu trả về của urls"
    
    print("Hoạt động tốt. Test thành công!")