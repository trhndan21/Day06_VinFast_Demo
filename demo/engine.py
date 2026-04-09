import json
import os
import streamlit as st
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph.message import add_messages
from typing import Annotated

from constants import (
    GUARDRAIL_MODEL, REASONING_MODEL, GUARDRAIL_PROMPT, SYSTEM_PROMPT,
    GUARDRAIL_RESPONSES, CONFIDENCE_THRESHOLD
)
from search import search_tavily

# We try to get API KEY from secrets, otherwise from os environs, otherwise empty string
api_key = ""
try:
    api_key = st.secrets["OPENAI_API_KEY"]
except (FileNotFoundError, KeyError, Exception):
    api_key = os.environ.get("OPENAI_API_KEY", "")

llm_mini = ChatOpenAI(model=GUARDRAIL_MODEL, temperature=0, api_key=api_key)
llm_main = ChatOpenAI(model=REASONING_MODEL, temperature=0, api_key=api_key)

class AgentState(TypedDict):
    input: str
    chat_history: List[str]
    category: str
    block_message: str | None
    
    messages: Annotated[list, add_messages]
    search_count: int
    
    answer: str
    confidence: int
    source_url: str
    suggest_human: bool
    suggest_reason: str

def node_guardrail(state: AgentState) -> AgentState:
    try:
        messages = [
            SystemMessage(content=GUARDRAIL_PROMPT),
            HumanMessage(content=state["input"])
        ]
        resp = llm_mini.invoke(messages, response_format={"type": "json_object"})
        result = json.loads(resp.content)
        category = result.get("category", "PASS")
    except Exception as e:
        print(f"Error in guardrail: {e}")
        category = "PASS"
        
    block_message = None
    if category != "PASS":
        block_message = GUARDRAIL_RESPONSES.get(category, GUARDRAIL_RESPONSES["OFF_TOPIC"])
        
    return {"category": category, "block_message": block_message}

from langchain_core.tools import tool

@tool
def search_web_tool(query: str) -> str:
    """Tìm kiếm thông tin xe VinFast trên internet. Bạn PHẢI tự rà soát ngữ cảnh lịch sử và truyền ĐỦ Chủ/Vị (đặc biệt Tên Dòng Xe đính kèm) vào tham số query."""
    result = search_tavily(query)
    snippets = result.get("snippets", [])
    urls = result.get("urls", [])
    if not snippets:
        return "Không tìm thấy thông tin."
    return "\n".join([f"[{i+1}] {s} (url: {urls[i] if i < len(urls) else 'N/A'})" for i, s in enumerate(snippets)])

def node_reasoning(state: AgentState) -> dict:
    messages = state.get("messages", [])
    search_count = state.get("search_count", 0)
    
    if not messages:
        history = state.get("chat_history", [])
        history_context = ""
        if history:
            history_context = "Lịch sử hội thoại:\n" + "\n".join(history) + "\n\n"
        user_content = f"{history_context}Câu hỏi hiện tại: {state['input']}"
        
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_content)
        ]
        
    # Bind tool chỉ cho phép tối đa 2 lần search (search_count = 0, 1 → allow; 2+ → disable)
    if search_count < 2:
        llm = llm_main.bind_tools([search_web_tool])
    else:
        llm = llm_main
        
    try:
        resp = llm.invoke(messages)
    except Exception as e:
        print("Lỗi Reasoning LLM:", e)
        resp = AIMessage(content=f'{{"answer": "Lỗi kết nối AI.", "confidence": 1, "source_url": "", "suggest_human": true, "suggest_reason": "Lỗi hệ thống."}}')
        
    return {"messages": [resp]}

def route_reasoning(state: AgentState) -> str:
    messages = state.get("messages", [])
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "parse_answer"

def node_tools(state: AgentState) -> dict:
    messages = state.get("messages", [])
    last_message = messages[-1]
    
    tool_messages = []
    if hasattr(last_message, "tool_calls"):
        for tool_call in last_message.tool_calls:
            query = tool_call["args"].get("query", "")
            print(f"-> Calling Tool Search: {query}")
            try:
                result = search_web_tool.invoke(tool_call["args"])
            except Exception as e:
                result = f"Tool Error: {e}"
            tool_messages.append(ToolMessage(
                content=str(result),
                tool_call_id=tool_call["id"],
                name=tool_call["name"]
            ))
            
    search_count = state.get("search_count", 0) + 1
    return {"messages": tool_messages, "search_count": search_count}

def node_parse_answer(state: AgentState) -> dict:
    messages = state.get("messages", [])
    last_message = messages[-1].content
    
    import re
    try:
        match = re.search(r'\{.*\}', last_message.strip(), re.DOTALL)
        if match:
            res_json = json.loads(match.group(0))
        else:
            res_json = json.loads(last_message)
            
        answer = res_json.get("answer", "Chưa tìm được thông tin.")
        conf = res_json.get("confidence", 5)
        url = res_json.get("source_url", "")
        s_human = conf < CONFIDENCE_THRESHOLD
        s_reason = res_json.get("suggest_reason", "Cần thông tin phân tích chuẩn hơn.")
        if s_human and not s_reason:
            s_reason = "Độ tin cậy của nguồn chưa đủ cao."
            
        return {
            "answer": answer, "confidence": conf, "source_url": url, 
            "suggest_human": s_human, "suggest_reason": s_reason
        }
    except Exception as e:
        print("Lỗi parse JSON final_answer:", e, " | Text raw:", last_message)
        return {
            "answer": last_message, "confidence": 5, "source_url": "", 
            "suggest_human": False, "suggest_reason": ""
        }

def route_after_guardrail(state: AgentState):
    if state.get("category") and state.get("category") != "PASS":
        return END
    return "reasoning"

workflow = StateGraph(AgentState)

workflow.add_node("guardrail", node_guardrail)
workflow.add_node("reasoning", node_reasoning)
workflow.add_node("tools", node_tools)
workflow.add_node("parse_answer", node_parse_answer)

workflow.set_entry_point("guardrail")

workflow.add_conditional_edges("guardrail", route_after_guardrail, {
    END: END,
    "reasoning": "reasoning"
})

workflow.add_conditional_edges("reasoning", route_reasoning, {
    "tools": "tools",
    "parse_answer": "parse_answer"
})

workflow.add_edge("tools", "reasoning")
workflow.add_edge("parse_answer", END)

agent_app = workflow.compile()

# --- Memory Management Utility ---
def summarize_memory(history: List[str]) -> str:
    """Tóm tắt lịch sử giao tiếp thành 1 chuỗi ngắn gọn"""
    if not history:
        return ""
    prompt = """Bạn là AI chuyên lưu trữ bộ nhớ (Memory). Hãy phân tích đoạn hội thoại dưới đây.
YÊU CẦU TỐI THƯỢNG:
- Dòng 1: KHẲNG ĐỊNH CHÍNH XÁC TÊN DÒNG XE VÀ PHIÊN BẢN (VD: Xe đang tư vấn: VinFast VF 8 Plus). 
- Dòng 2: Tóm tắt ngắn gọn nội dung và thắc mắc cốt lõi.

VÍ DỤ TÓM TẮT (Few-shot):
Lịch sử Chat:
User: VF 8 bản pin cao nhất giá sao?
AI: Dạ bản Plus giá khoảng...
User: Pin sạc đầy tốn bao lâu?
AI: Khoảng 45 phút cho mức 10-70% pin.
==>
Tóm tắt kết quả:
Xe đang tư vấn: VinFast VF 8 bản Plus
Nội dung: Người dùng quan tâm giá cả và thời gian sạc đầy pin.

Lịch sử Chat thực tế:
""" + "\n".join(history)
    messages = [HumanMessage(content=prompt)]
    try:
        resp = llm_mini.invoke(messages)
        return resp.content
    except Exception as e:
        print(f"Lỗi tóm tắt bộ nhớ: {e}")
        return "Lịch sử cũ đã được lưu but gặp lỗi tóm tắt."
