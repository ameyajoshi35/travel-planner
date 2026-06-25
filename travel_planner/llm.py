"""
LLM layer — powered by LangChain + Groq.

Key components:
  ChatGroq              — Groq-hosted LLaMA 3.3 70B via LangChain's chat model interface
  ChatPromptTemplate    — structured prompt construction (system + human turns)
  JsonOutputParser      — parses the LLM's JSON-mode output into a Python dict
  synthesize_json()     — hardened call: injection defense → LCEL chain → validate → repair retry
"""

import json
import re
from typing import Callable, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from . import guards
from .models import TripContext
from .prompts import (
    CONFIRMATION_TEMPLATE,
    EXTRACT_SYSTEM,
    RESPONSE_SYSTEM_TEMPLATE,
)

MODEL = "llama-3.3-70b-versatile"


# ── LLM factory ───────────────────────────────────────────────────────────────

def get_llm(max_tokens: int = 2048, temperature: float = 0) -> ChatGroq:
    """
    Return a ChatGroq instance in JSON mode.

    JSON mode (response_format) guarantees the model's reply is valid JSON,
    which makes JsonOutputParser reliable downstream.
    """
    return ChatGroq(
        model=MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


# ── JSON parsing helper (kept for edge-case fallback use) ─────────────────────

def parse_json(s) -> Optional[dict]:
    """Parse JSON from a string, tolerating markdown fences and trailing commas."""
    if isinstance(s, dict):
        return s
    s = re.sub(r"```(?:json)?", "", str(s)).strip()
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s = s[start: end + 1]
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        fixed = re.sub(r",(\s*[}\]])", r"\1", s)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            return None


# ── Core synthesis function ───────────────────────────────────────────────────

def synthesize_json(
    system: str,
    user_content: str,
    validate_fn: Callable,
    max_tokens: int,
) -> Optional[dict]:
    """
    Hardened LLM call using LangChain LCEL:

      ChatPromptTemplate  →  ChatGroq (JSON mode)  →  JsonOutputParser
                                                            │
                                                     validate_fn()
                                                            │
                                              ┌─── valid ───┴─── invalid ───┐
                                           return           repair turn (retry once)

    The system prompt is prefixed with INJECTION_DEFENSE so the model treats
    Tavily search results as untrusted data, not instructions.
    """
    system_with_defense = guards.INJECTION_DEFENSE + system

    # Primary LCEL chain
    prompt = ChatPromptTemplate.from_messages([
        ("system", "{system}"),
        ("human", "{user_content}"),
    ])
    llm = get_llm(max_tokens=max_tokens)
    chain = prompt | llm | JsonOutputParser()

    try:
        raw = chain.invoke({"system": system_with_defense, "user_content": user_content})
    except Exception:
        raw = {}

    clean = validate_fn(raw if isinstance(raw, dict) else None)
    if clean is not None:
        return clean

    # Repair turn: give the model its bad output and ask it to fix
    repair_prompt = ChatPromptTemplate.from_messages([
        ("system", "{system}"),
        ("human", "{user_content}"),
        ("ai", "{bad_response}"),
        ("human", (
            "Your previous response was not valid JSON matching the required schema. "
            "Return ONLY a single valid JSON object matching the schema exactly — "
            "no prose, no markdown, no code fences."
        )),
    ])
    repair_chain = repair_prompt | llm | JsonOutputParser()

    try:
        raw2 = repair_chain.invoke({
            "system": system_with_defense,
            "user_content": user_content,
            "bad_response": json.dumps(raw) if isinstance(raw, dict) else str(raw),
        })
        return validate_fn(raw2 if isinstance(raw2, dict) else None)
    except Exception:
        return None


# ── Chatbot functions (used by form-filling flow in main.py) ──────────────────

def extract_inputs(user_message: str, trip_context: TripContext) -> dict:
    """
    Extract structured trip fields from a user message using an LCEL chain.
    Returns a partial dict of TripContext fields (only those mentioned).
    """
    user_content = f"Current context: {trip_context.to_json()}\nUser said: {user_message}"

    prompt = ChatPromptTemplate.from_messages([
        ("system", EXTRACT_SYSTEM),
        ("human", "{user_content}"),
    ])
    # Use JSON mode so JsonOutputParser always gets valid JSON
    chain = prompt | get_llm(max_tokens=512) | JsonOutputParser()

    try:
        return chain.invoke({"user_content": user_content})
    except Exception:
        return {}


def generate_response(
    trip_context: TripContext,
    user_message: str,
    conversation_history: List[dict],
) -> str:
    """
    Generate the next conversational reply, asking for the next missing field.
    Uses LangChain message objects so the full conversation history is preserved.
    """
    system = RESPONSE_SYSTEM_TEMPLATE.format(
        missing_fields=", ".join(trip_context.missing_fields()) or "none",
        trip_context_json=trip_context.to_json(),
    )

    # Build message list: system + alternating history + new user turn
    messages = [SystemMessage(content=system)]
    for msg in conversation_history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=user_message))

    # Plain chat (not JSON mode — this is a natural-language reply)
    llm = ChatGroq(model=MODEL, temperature=0.4, max_tokens=1024)
    return llm.invoke(messages).content.strip()


def generate_confirmation(trip_context: TripContext) -> str:
    """Deterministic summary — no LLM call needed."""
    ctx = trip_context

    if ctx.traveler_type == "solo":
        travelers_summary = "Solo traveler"
    elif ctx.num_travelers is not None:
        travelers_summary = f"{ctx.num_travelers} {ctx.traveler_type or 'travelers'}"
    else:
        travelers_summary = ctx.traveler_type or "unknown"

    if ctx.has_kids and ctx.kids_ages:
        travelers_summary += f" (kids: {', '.join(str(a) for a in ctx.kids_ages)} yrs)"
    elif ctx.has_kids:
        travelers_summary += " (with kids)"

    dates_summary = ctx.travel_dates or f"{ctx.duration_days} days in {ctx.travel_month}"
    vibe = ", ".join(ctx.experience_type) if ctx.experience_type else "open"

    kids_line = ""
    if ctx.has_kids and ctx.kids_ages:
        kids_line = f"\n - Kids: {', '.join(str(a) for a in ctx.kids_ages)} yrs old"

    constraints_line = ""
    if ctx.constraints:
        constraints_line = f"\n - Constraints: {', '.join(ctx.constraints)}"
    if ctx.has_elderly:
        constraints_line += "\n - Elderly travelers included"

    destination_line = ""
    if ctx.destination:
        destination_line = f"\n - Destination: {ctx.destination}"

    return CONFIRMATION_TEMPLATE.format(
        travelers_summary=travelers_summary,
        dates_summary=dates_summary,
        starting_city=ctx.starting_city,
        budget=f"{ctx.budget_total:,}",
        vibe=vibe,
        kids_line=kids_line,
        constraints_line=constraints_line,
        destination_line=destination_line,
    )
