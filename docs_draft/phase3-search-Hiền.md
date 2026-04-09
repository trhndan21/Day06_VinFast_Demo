# Phase 3 — Search (`search.py`)

> Đọc `CONTEXT.md` trước. File này chỉ mô tả phần Phase 3 đảm nhiệm.

---

## Nhiệm vụ

Xây dựng `search.py`:
- Kiểm tra Verified Cache (`cache.json`) trước khi gọi DDG
- Fetch DuckDuckGo Instant Answer API → parse kết quả
- `add_to_cache()` để Phase 5 (Admin) ghi cache mới

**Không** chứa logic AI, không Streamlit UI, không OPENAI.
Chỉ HTTP request + file JSON read/write.

---

## Hàm 1 — `check_cache(query)`

```
Input  : query: str (raw)
Output : { "hit": bool, "entry": dict | None }
```

```python
import json, os
from constants import CACHE_FILE

def _normalize(q: str) -> str:
    """lowercase, trim, bỏ dấu câu cuối"""
    import re
    return re.sub(r"[?!.,]+$", "", q.lower().strip())

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
```

**Lưu ý:** Match exact normalized query. Không fuzzy match — giữ đơn giản.

---

## Hàm 2 — `search_ddg(query)`

```
Input  : query: str
Output : { "snippets": list[str], "urls": list[str] }
         Tối đa 3 snippets. Trả về rỗng nếu lỗi (không raise exception).
```

```python
import requests
from constants import DDG_API

def search_ddg(query: str) -> dict:
    try:
        params = {
            "q"              : f"vinfast {query}",
            "format"         : "json",
            "no_html"        : "1",
            "skip_disambig"  : "1",
        }
        resp = requests.get(DDG_API, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return _parse_ddg(data)
    except Exception:
        return {"snippets": [], "urls": []}

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
```

---

## Hàm 3 — `add_to_cache(query, answer, source_url)`

```
Input  : query: str, answer: str, source_url: str
Output : None
Gọi bởi: Phase 5 (Admin) khi admin verify một Q&A
```

```python
import json, os
from datetime import datetime, timezone
from constants import CACHE_FILE

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
```

---

## Hàm 4 — `get_all_cache()`

```
Input  : None
Output : list[dict]   ← danh sách tất cả cache entries
Gọi bởi: Phase 5 (Admin) để hiển thị + xóa
```

```python
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
```

---

## Xử lý lỗi

| Tình huống | Hành vi |
|-----------|---------|
| DDG timeout (> 5s) | `requests.get(..., timeout=5)` → catch → `{snippets:[], urls:[]}` |
| DDG trả 4xx/5xx | `raise_for_status()` → catch → empty |
| `cache.json` corrupt | `except Exception` → return `[]` hoặc `{"hit":False}` |
| Không có internet | Catch requests exception → empty snippets |

---

## Offline/Demo Mode

Thêm flag ở đầu file nếu cần demo offline:

```python
OFFLINE_MODE = False   # set True khi không có internet

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

def search_ddg(query: str) -> dict:
    if OFFLINE_MODE:
        norm = _normalize(query)
        return MOCK_DATA.get(norm, {"snippets": [], "urls": []})
    # ... real implementation above
```

---

## Kiểm tra xong Phase 3

```python
# Test không cần API key
from search import check_cache, search_ddg, add_to_cache, _normalize

# Normalize
assert _normalize("VF 8 giá bao nhiêu???") == "vf 8 giá bao nhiêu"

# Cache miss khi chưa có file
result = check_cache("VF 8 giá bao nhiêu")
assert result["hit"] == False

# Add to cache
add_to_cache("VF 8 giá bao nhiêu", "VF 8 Eco 1.057 tỷ...", "https://vinfastautovn.com/vf8")

# Cache hit
result2 = check_cache("VF 8 giá bao nhiêu")
assert result2["hit"] == True
assert "answer" in result2["entry"]

# DDG search (cần internet)
data = search_ddg("vf 8")
assert isinstance(data["snippets"], list)
assert isinstance(data["urls"], list)
```
