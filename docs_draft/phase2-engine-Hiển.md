# Phase 2 — AI Engine (`engine.py` - AI Agent với LangGraph)

> Đọc `CONTEXT.md` trước. 

---

## Nhiệm vụ

Xây dựng `engine.py` sử dụng thư viện **LangGraph** để xây dựng Agent theo mô hình StateGraph.
Các bước (Nodes) trong Graph:
1. `node_guardrail`: Phân loại input.
2. `node_cache_check`: Kiểm tra Verified Cache (dùng hàm từ Phase 3).
3. `node_ddg_search`: Tìm kiếm thông tin thực tế (dùng hàm từ Phase 3).
4. `node_reasoning`: Tổng hợp, tự chấm điểm.

---

## Constants (giữ nguyên)
`(Phase 2 vẫn import các prompt từ Constants như bản trước)`

---

## 1. Định nghĩa Agent State

Định nghĩa cấu trúc dữ liệu lưu chuyển giữa các Nodes thông qua `TypedDict`.

```python
import json
import streamlit as st
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from constants import (
    GUARDRAIL_MODEL, REASONING_MODEL, GUARDRAIL_PROMPT, SYSTEM_PROMPT,
    GUARDRAIL_RESPONSES, CONFIDENCE_THRESHOLD
)
from search import check_cache, search_ddg

# Khởi tạo models
llm_mini = ChatOpenAI(model=GUARDRAIL_MODEL, temperature=0, api_key=st.secrets.get("OPENAI_API_KEY", ""))
llm_main = ChatOpenAI(model=REASONING_MODEL, temperature=0.3, api_key=st.secrets.get("OPENAI_API_KEY", ""))

class AgentState(TypedDict):
    input: str
    
    # Kết quả Guardrail
    category: str
    block_message: str | None
    
    # Kết quả Cache
    cache_hit: bool
    
    # Kết quả DDG Search
    snippets: List[str]
    urls: List[str]
    
    # Kết quả Reasoning
    answer: str
    confidence: int
    source_url: str
    suggest_human: bool
    suggest_reason: str
```

---

## 2. Định nghĩa Nodes

**Node 1: node_guardrail**
```python
def node_guardrail(state: AgentState) -> AgentState:
    try:
        messages = [
            SystemMessage(content=GUARDRAIL_PROMPT),
            HumanMessage(content=state["input"])
        ]
        # Ép model trả về JSON object
        resp = llm_mini.invoke(messages, response_format={"type": "json_object"})
        result = json.loads(resp.content)
        category = result.get("category", "PASS")
    except Exception:
        category = "PASS"
        
    block_message = None
    if category != "PASS":
        block_message = GUARDRAIL_RESPONSES.get(category, GUARDRAIL_RESPONSES["OFF_TOPIC"])
        
    return {"category": category, "block_message": block_message}
```

**Node 2: node_cache_check**
```python
def node_cache_check(state: AgentState) -> AgentState:
    cached = check_cache(state["input"])
    if cached["hit"]:
        return {
            "cache_hit": True,
            "answer": cached["entry"]["answer"],
            "source_url": cached["entry"].get("source_url", ""),
            "confidence": 10,
            "suggest_human": False,
            "suggest_reason": ""
        }
    return {"cache_hit": False}
```

**Node 3: node_ddg_search**
```python
def node_ddg_search(state: AgentState) -> AgentState:
    search_result = search_ddg(state["input"])
    return {
        "snippets": search_result["snippets"], 
        "urls": search_result["urls"]
    }
```

**Node 4: node_reasoning**
```python
def node_reasoning(state: AgentState) -> AgentState:
    snippets = state.get("snippets", [])
    urls = state.get("urls", [])
    
    if snippets:
        search_context = "\n".join([f"[{i+1}] {s} (url: {urls[i] if i < len(urls) else 'N/A'})" for i, s in enumerate(snippets)])
    else:
        search_context = "Không tìm thấy kết quả từ DDG."
        
    user_content = f"Câu hỏi: {state['input']}\n\nSearch Results:\n{search_context}"
    
    try:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_content)
        ]
        resp = llm_main.invoke(messages, response_format={"type": "json_object"})
        res_json = json.loads(resp.content)
        
        answer = res_json.get("answer", "Chưa tìm được thông tin.")
        conf = res_json.get("confidence", 5)
        url = res_json.get("source_url", urls[0] if urls else "")
        s_human = conf < CONFIDENCE_THRESHOLD
        s_reason = res_json.get("suggest_reason", "Cần tra cứu thêm.")
        if s_human and not s_reason:
            s_reason = "Độ tin cậy của nguồn thông tin chưa cao."
            
        return {
            "answer": answer, "confidence": conf, "source_url": url, 
            "suggest_human": s_human, "suggest_reason": s_reason
        }
    except Exception:
         return {
            "answer": "Hệ thống đang lỗi kết nối AI, anh/chị thử lại sau nhé.",
            "confidence": 1, "source_url": "", 
            "suggest_human": True, "suggest_reason": "Lỗi kỹ thuật"
        }
```

---

## 3. Build & Compile LangGraph

Xác định cách các state luân chuyển.

```python
# Edges: Conditional routers
def route_after_guardrail(state: AgentState):
    if state.get("category") != "PASS":
        return END
    return "cache_check"

def route_after_cache(state: AgentState):
    if state.get("cache_hit"):
        return END
    return "ddg_search"

# Khởi tạo Graph
workflow = StateGraph(AgentState)

# Gắn Nodes
workflow.add_node("guardrail", node_guardrail)
workflow.add_node("cache_check", node_cache_check)
workflow.add_node("ddg_search", node_ddg_search)
workflow.add_node("reasoning", node_reasoning)

# Thiết lập Edges
workflow.set_entry_point("guardrail")

workflow.add_conditional_edges("guardrail", route_after_guardrail, {
    END: END,
    "cache_check": "cache_check"
})

workflow.add_conditional_edges("cache_check", route_after_cache, {
    END: END,
    "ddg_search": "ddg_search"
})

workflow.add_edge("ddg_search", "reasoning")
workflow.add_edge("reasoning", END)

# Compile Graph
agent_app = workflow.compile()
```

Từ nay Phase 1 (`app.py`) sẽ chỉ cần import `agent_app` và gọi lệnh:
`final_state = agent_app.invoke({"input": user_prompt})`
Cả flow sẽ tự động block tin toxic, gọi cache, hoặc fetch DDG và sinh kết quả cực kỳ bảo mật và mạch lạc.
