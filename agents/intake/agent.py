import json
import os
from typing import TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from agents.common.schemas import IntakeResult
from agents.intake.prompts import FEW_SHOT_EXAMPLES, SYSTEM_PROMPT

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


class IntakeState(TypedDict):
    user_request: str
    result: IntakeResult | None
    error: str | None


def _build_messages(user_request: str) -> list:
    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for ex in FEW_SHOT_EXAMPLES:
        messages.append(HumanMessage(content=f"REQUEST:\n{ex['input']}"))
        messages.append(
            SystemMessage(
                content=f"EXAMPLE_OUTPUT:\n{json.dumps(ex['output'], indent=2)}"
            )
        )
    messages.append(
        HumanMessage(
            content=(
                f"REQUEST:\n{user_request}\n\n"
                f"Extract and return JSON matching the IntakeResult schema. "
                f"Include 'raw_request' field with the original request text."
            )
        )
    )
    return messages


def extract_node(state: IntakeState) -> IntakeState:
    """Single LLM call to extract structured data."""
    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    messages = _build_messages(state["user_request"])

    try:
        response = llm.invoke(messages)
        data = json.loads(response.content)
        data["raw_request"] = state["user_request"]
        result = IntakeResult(**data)
        return {"user_request": state["user_request"], "result": result, "error": None}
    except Exception as e:
        return {
            "user_request": state["user_request"],
            "result": None,
            "error": f"{type(e).__name__}: {e}",
        }


def build_intake_graph():
    graph = StateGraph(IntakeState)
    graph.add_node("extract", extract_node)
    graph.set_entry_point("extract")
    graph.add_edge("extract", END)
    return graph.compile()


def run_intake(user_request: str) -> IntakeResult:
    """Convenience: run the agent on a single request."""
    app = build_intake_graph()
    final = app.invoke({"user_request": user_request, "result": None, "error": None})
    if final.get("error"):
        raise RuntimeError(final["error"])
    return final["result"]
