# Stub dùng để test Phase 1 khi engine.py (Phase 2) chưa sẵn.
# Xóa file này và dùng engine.py thật khi Phase 2 hoàn thành.

class _MockAgentApp:
    def invoke(self, state: dict) -> dict:
        query = state.get("input", "")
        # Giả lập suggest_human khi câu hỏi chứa từ "bảo hành sạc"
        if "bảo hành" in query and "sạc" in query:
            return {
                "answer": "[STUB] Chính sách bảo hành khi sạc bên thứ 3 cần xác nhận thêm từ đại lý.",
                "confidence": 5,
                "source_url": "",
                "suggest_human": True,
                "suggest_reason": "Chính sách phụ thuộc hợp đồng bảo hành riêng, em chưa có thông tin chính xác.",
                "block_message": None,
                "cache_hit": False,
            }
        return {
            "answer": f"[STUB] Câu trả lời mẫu cho: «{query}»",
            "confidence": 8,
            "source_url": "https://vinfastautovn.com",
            "suggest_human": False,
            "suggest_reason": "",
            "block_message": None,
            "cache_hit": False,
        }


agent_app = _MockAgentApp()
