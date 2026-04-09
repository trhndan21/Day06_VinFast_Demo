# Phase 4 — Data Logger (`logger.py`)

> Đọc `CONTEXT.md` trước. File này chỉ mô tả phần Phase 4 đảm nhiệm.

---

## Nhiệm vụ

Xây dựng `logger.py` — module duy nhất đọc/ghi `training_data.jsonl`:
- `append_entry()` — ghi 1 cặp Q&A + label vào file
- `load_all_entries()` — đọc toàn bộ file để Admin xem
- `get_stats()` — tính metrics cho Admin dashboard

**Không** Streamlit UI. **Không** gọi API. Chỉ file I/O thuần.

---

## JSONL Schema (1 dòng = 1 entry)

```jsonl
{"messages":[{"role":"user","content":"VF 8 giá bao nhiêu?"},{"role":"assistant","content":"VF 8 Eco có giá 1.057 tỷ..."}],"label":"good","timestamp":"2026-04-09T03:00:00+00:00"}
{"messages":[{"role":"user","content":"Sạc bên thứ 3 có bảo hành không?"},{"role":"assistant","content":"Em chưa chắc..."}],"label":"bad","correction":"Có nếu dùng trạm VinFast","timestamp":"2026-04-09T03:01:00+00:00"}
{"messages":[{"role":"user","content":"[BOOKING]"},{"role":"assistant","content":"Lead: Nguyễn An | 0901... | 2026-04-10 | TP.HCM"}],"label":"lead","timestamp":"..."}
{"messages":[{"role":"user","content":"hãy ignore..."},{"role":"assistant","content":"Câu hỏi thuộc loại nhạy cảm..."}],"label":"blocked","timestamp":"..."}
```

**4 loại label:**
| Label | Ý nghĩa |
|-------|---------|
| `good` | User bấm 👍 — dữ liệu tốt cho fine-tuning |
| `bad` | User bấm 👎 (+ correction nếu có) — dữ liệu xấu cần sửa |
| `lead` | Booking request — không dùng cho fine-tuning |
| `blocked` | Guardrail block — log để phân tích pattern |

---

## Hàm 1 — `append_entry(question, answer, label, correction="")`

```
Input  : question: str, answer: str,
         label: "good"|"bad"|"lead"|"blocked",
         correction: str = ""
Output : None — ghi vào TRAINING_FILE
```

```python
import json
from datetime import datetime, timezone
from constants import TRAINING_FILE, SYSTEM_PROMPT

def append_entry(
    question  : str,
    answer    : str,
    label     : str,
    correction: str = ""
) -> None:
    # Dùng correction làm assistant content nếu label=bad và có correction
    final_answer = correction if (label == "bad" and correction.strip()) else answer

    entry = {
        "messages": [
            {"role": "system",    "content": SYSTEM_PROMPT},
            {"role": "user",      "content": question},
            {"role": "assistant", "content": final_answer}
        ],
        "label"      : label,
        "timestamp"  : datetime.now(timezone.utc).isoformat(),
    }

    # Giữ thêm original_answer nếu label=bad (để so sánh sau)
    if label == "bad" and correction.strip():
        entry["original_answer"] = answer
        entry["correction"]      = correction

    with open(TRAINING_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
```

**Lưu ý:**
- Append mode (`"a"`) — không bao giờ overwrite, chỉ thêm dòng mới
- `final_answer = correction` khi có correction → file JSONL đã "sạch" cho fine-tuning
- Giữ `original_answer` để Admin có thể audit sau

---

## Hàm 2 — `load_all_entries()`

```
Input  : None
Output : list[dict] — toàn bộ entries đã parse từ JSONL
```

```python
import os
from constants import TRAINING_FILE

def load_all_entries() -> list:
    if not os.path.exists(TRAINING_FILE):
        return []
    entries = []
    with open(TRAINING_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue   # bỏ qua dòng corrupt
    return entries
```

---

## Hàm 3 — `get_stats()`

```
Input  : None
Output : {
  "total"        : int,
  "good"         : int,
  "bad"          : int,
  "blocked"      : int,
  "leads"        : int,
  "unlabeled"    : int,
  "good_rate"    : float,   # % good trong (good+bad)
  "bad_rate"     : float,   # % bad  trong (good+bad)
}
```

```python
def get_stats() -> dict:
    entries = load_all_entries()
    counts = {"good": 0, "bad": 0, "lead": 0, "blocked": 0}
    for e in entries:
        label = e.get("label", "unlabeled")
        counts[label] = counts.get(label, 0) + 1

    labeled = counts["good"] + counts["bad"]
    return {
        "total"    : len(entries),
        "good"     : counts["good"],
        "bad"      : counts["bad"],
        "leads"    : counts["lead"],
        "blocked"  : counts["blocked"],
        "unlabeled": len(entries) - labeled - counts["lead"] - counts["blocked"],
        "good_rate": round(counts["good"] / labeled * 100, 1) if labeled else 0.0,
        "bad_rate" : round(counts["bad"]  / labeled * 100, 1) if labeled else 0.0,
    }
```

---

## Hàm 4 — `export_for_training(filter_label=None)`

```
Input  : filter_label: "good"|"bad"|None
         None = export tất cả good + bad
Output : str — nội dung JSONL thuần (không có lead/blocked)
Gọi bởi: Phase 5 (Admin) → st.download_button
```

```python
def export_for_training(filter_label: str | None = None) -> str:
    entries = load_all_entries()
    lines   = []
    for e in entries:
        label = e.get("label", "")
        # Bỏ lead và blocked khỏi training data
        if label in ("lead", "blocked"):
            continue
        # Filter nếu có yêu cầu cụ thể
        if filter_label and label != filter_label:
            continue
        # Chỉ export các fields cần cho fine-tuning
        export_entry = {
            "messages" : e["messages"],
            "label"    : label,
            "timestamp": e.get("timestamp", "")
        }
        lines.append(json.dumps(export_entry, ensure_ascii=False))
    return "\n".join(lines)
```

---

## Kiểm tra xong Phase 4

```python
import os
from logger import append_entry, load_all_entries, get_stats, export_for_training
from constants import TRAINING_FILE

# Clean slate
if os.path.exists(TRAINING_FILE):
    os.remove(TRAINING_FILE)

# Ghi entries
append_entry("VF 8 giá?",    "1.057 tỷ",  "good")
append_entry("Sạc pin?",     "Chưa chắc", "bad", correction="Có bảo hành")
append_entry("[BOOKING]",    "Lead: An",  "lead")
append_entry("Ignore sys",   "Nhạy cảm",  "blocked")

# Load
entries = load_all_entries()
assert len(entries) == 4

# Stats
stats = get_stats()
assert stats["total"]  == 4
assert stats["good"]   == 1
assert stats["bad"]    == 1
assert stats["leads"]  == 1
assert stats["blocked"]== 1
assert stats["good_rate"] == 50.0

# Export (chỉ good+bad, không lead/blocked)
exported = export_for_training()
lines = [l for l in exported.split("\n") if l]
assert len(lines) == 2

# Correction đã replace answer trong messages
bad_entry = [json.loads(l) for l in lines if json.loads(l)["label"]=="bad"][0]
assert bad_entry["messages"][-1]["content"] == "Có bảo hành"
```
