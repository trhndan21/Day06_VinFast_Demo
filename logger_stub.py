# Stub dùng để test Phase 1 khi logger.py (Phase 4) chưa sẵn.
# Xóa file này và dùng logger.py thật khi Phase 4 hoàn thành.

def append_entry(question: str, answer: str, label: str, correction: str = "") -> None:
    # no-op: chỉ in ra console để debug
    print(f"[logger_stub] label={label} | q={question[:40]!r}")
