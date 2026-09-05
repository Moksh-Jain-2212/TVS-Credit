"""Borrower-facing, explanation-only Ask NADI assistant.

The assistant receives a de-identified underwriting summary and can explain the
already persisted result. It cannot invoke, update, or override underwriting.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from langchain_core.prompts import ChatPromptTemplate

from app.models import LoanApplication
from app.services.grok_explainability import deidentified_input, truthy


ASSISTANT_PROMPT_VERSION = "ask-nadi-borrower-v2"
DISCLAIMER = "Ask NADI explains an existing assessment. It cannot approve, reject, change, or promise a loan decision."

PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are Ask NADI, a borrower-facing explanation assistant for an existing lending assessment.
Answer only from the supplied de-identified underwriting context.
Use plain, respectful language and INR amounts when supplied. Be genuinely helpful and descriptive, without repeating generic disclaimers.
Never make, change, promise, or recommend a lending decision. Never say that connecting data guarantees approval.
Do not provide financial, legal, or investment advice. Do not infer protected characteristics or mention raw counterparties.
If asked to change a decision, say only a future re-underwriting after new consented evidence or repayment observations can change eligibility.
Use this exact structure, with short sections and only facts supported by the context:
Current assessment: Explain the decision and whether it concerns the full request or a safer alternative.
Why NADI reached this result: Give 2-4 concrete decision reasons.
What this means for you: Explain the practical impact, including recommended amount or evidence confidence when available.
What you can do next: Give 1-3 realistic next steps. Never promise a different outcome.
Keep the answer under 220 words and end with: "NADI's policy engine, not this assistant, makes lending decisions.""" ,
        ),
        (
            "human",
            "Question: {question}\n\nDe-identified underwriting context:\n{context}",
        ),
    ]
)


def _clean_question(question: str) -> str:
    return " ".join(question.strip().split())[:500]


def _inr(value: Any) -> str:
    try:
        return f"INR {float(value):,.0f}"
    except (TypeError, ValueError):
        return "not available"


def fallback_answer(question: str, context: dict[str, Any]) -> str:
    underwriting = context["underwriting"]
    lowered = question.lower()
    decision = str(underwriting.get("nadi_decision_state") or "pending").replace("_", " ")
    recommended = underwriting.get("recommended_amount")
    confidence = underwriting.get("confidence_score")
    reasons = [str(reason).rstrip(".") for reason in underwriting.get("decision_reasons") or []]
    active_sources = [
        str(source.get("source_type", "")).replace("_", " ").title()
        for source in context.get("behavioral_sources", [])
        if source.get("active")
    ]
    recommended_text = _inr(recommended) if recommended is not None else "not available"
    confidence_text = f"{int(float(confidence))}/100" if confidence is not None else "not available"
    if any(term in lowered for term in ("change", "override", "approve me", "increase", "guarantee")):
        return (
            f"Current assessment:\nYour current NADI result is {decision}. I cannot change or promise this result, and I cannot override it.\n\n"
            "What you can do next:\nA future assessment can consider new consented evidence or repayment observations through complete re-underwriting. "
            "More data does not guarantee approval because affordability and stress checks still apply.\n\n"
            "NADI's policy engine, not this assistant, makes lending decisions."
        )

    reason_lines = reasons[:3] or ["NADI considers affordability, repayment risk, evidence confidence, and stress resilience together"]
    reason_text = "\n".join(f"- {reason}." for reason in reason_lines)
    source_text = ", ".join(active_sources) if active_sources else "No alternative-data source is currently connected"
    if "safe to learn" in decision.lower():
        meaning = f"The full request is not considered safely supportable today. A smaller starter exposure of {recommended_text} may be considered if it remains within the repayment envelope."
    elif "approve" in decision.lower():
        meaning = f"NADI found that the current request fits the available repayment and evidence assessment. The recommended amount is {recommended_text}."
    elif "evidence" in decision.lower():
        meaning = "NADI needs stronger or more complete evidence before it can make a confident affordability assessment."
    else:
        meaning = "NADI found that the current request does not fit the available repayment-capacity and stress assessment."
    next_steps = (
        "- Keep consented financial evidence accurate and complete.\n"
        "- Build repayment observations over time where a starter path is offered.\n"
        "- Review the recommended amount and tenure rather than assuming the full requested amount is safe."
    )
    return (
        f"Current assessment:\nYour current NADI result is {decision}.\n\n"
        f"Why NADI reached this result:\n{reason_text}\n\n"
        f"What this means for you:\n{meaning} Evidence confidence is {confidence_text}. Connected evidence: {source_text}.\n\n"
        f"What you can do next:\n{next_steps}\n\n"
        "NADI's policy engine, not this assistant, makes lending decisions."
    )


def answer_question(session: Any, application: LoanApplication, question: str) -> dict[str, Any]:
    clean_question = _clean_question(question)
    context = deidentified_input(session, application)
    if not clean_question:
        return {"answer": "Please ask a question about this application. " + DISCLAIMER, "provider": "fallback", "prompt_version": ASSISTANT_PROMPT_VERSION, "disclaimer": DISCLAIMER}
    if not (os.getenv("XAI_API_KEY", "").strip() and truthy(os.getenv("GROK_EXPLANATION_ENABLED"))):
        return {"answer": fallback_answer(clean_question, context), "provider": "fallback", "prompt_version": ASSISTANT_PROMPT_VERSION, "disclaimer": DISCLAIMER}
    messages = PROMPT.format_messages(question=clean_question, context=json.dumps(context, sort_keys=True, default=str))
    try:
        response = httpx.post(
            f"{os.getenv('XAI_BASE_URL', 'https://api.x.ai/v1').rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['XAI_API_KEY']}", "Content-Type": "application/json"},
            json={
                "model": os.getenv("XAI_MODEL", "grok-4.6"),
                "messages": [
                    {"role": "user" if message.type == "human" else message.type, "content": str(message.content)}
                    for message in messages
                ],
                "temperature": 0.2,
                "max_tokens": 220,
            },
            timeout=20,
        )
        response.raise_for_status()
        answer = str(response.json()["choices"][0]["message"]["content"]).strip()
        if not answer:
            raise ValueError("empty assistant response")
        return {"answer": answer, "provider": "xAI", "prompt_version": ASSISTANT_PROMPT_VERSION, "disclaimer": DISCLAIMER}
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return {"answer": fallback_answer(clean_question, context), "provider": "fallback", "prompt_version": ASSISTANT_PROMPT_VERSION, "disclaimer": DISCLAIMER}
