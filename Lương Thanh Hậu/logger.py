import json
import os
from datetime import datetime, timezone

from constants import TRAINING_FILE, SYSTEM_PROMPT


def append_entry(
    question  : str,
    answer    : str,
    label     : str,
    correction: str = ""
) -> None:
    # Use correction as assistant content if label=bad and correction provided
    final_answer = correction if (label == "bad" and correction.strip()) else answer

    entry = {
        "messages": [
            {"role": "system",    "content": SYSTEM_PROMPT},
            {"role": "user",      "content": question},
            {"role": "assistant", "content": final_answer}
        ],
        "label"    : label,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Keep original_answer if label=bad and correction provided (for audit)
    if label == "bad" and correction.strip():
        entry["original_answer"] = answer
        entry["correction"]      = correction

    with open(TRAINING_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


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
                continue  # skip corrupt lines
    return entries


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


def export_for_training(filter_label: str | None = None) -> str:
    entries = load_all_entries()
    lines   = []
    for e in entries:
        label = e.get("label", "")
        # Exclude lead and blocked from training data
        if label in ("lead", "blocked"):
            continue
        # Apply specific label filter if requested
        if filter_label and label != filter_label:
            continue
        # Only export fields needed for fine-tuning
        export_entry = {
            "messages" : e["messages"],
            "label"    : label,
            "timestamp": e.get("timestamp", "")
        }
        lines.append(json.dumps(export_entry, ensure_ascii=False))
    return "\n".join(lines)
