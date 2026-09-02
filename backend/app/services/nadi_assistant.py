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


ASSISTANT_PROMPT_VERSION = "ask-nadi-borrower-v1"
DISCLAIMER = "Ask NADI explains an existing assessment. It cannot approve, reject, change, or promise a loan decision."

PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are Ask NADI, a borrower-facing explanation assistant for an existing lending assessment.
Answer only from the supplied de-identified underwriting context.
Use plain, respectful language and INR amounts when supplied.
Never make, change, promise, or recommend a lending decision. Never say that connecting data guarantees approval.
Do not provide financial, legal, or investment advice. Do not infer protected characteristics or mention raw counterparties.
If asked to change a decision, say only a future re-underwriting after new consented evidence or repayment observations can change eligibility.
Keep the answer under 120 words and end with: "NADI's policy engine, not this assistant, makes lending decisions.""" ,
        ),
        (
            "human",
            "Question: {question}\n\nDe-identified underwriting context:\n{context}",
        ),
    ]
)


def _clean_question(question: str) -> str:
    return " ".join(question.strip().split())[:500]


def fallback_answer(question: str, context: dict[str, Any]) -> str:
    underwriting = context["underwriting"]
    lowered = question.lower()
    decision = str(underwriting.get("nadi_decision_state") or "pending").replace("_", " ")
    recommended = underwriting.get("recommended_amount")
    confidence = underwriting.get("confidence_score")
    reasons = underwriting.get("decision_reasons") or []
    if any(term in lowered for term in ("change", "override", "approve me", "increase", "guarantee")):
        answer = "I cannot change or promise this result. New consented evidence or repayment observations can be considered only through a complete re-underwriting."
    elif any(term in lowered for term in ("why", "reason", "decision")):
        answer = f"Your current NADI result is {decision}. " + (str(reasons[0]) if reasons else "It is based on affordability, risk, evidence confidence, and stress testing.")
    elif any(term in lowered for term in ("improve", "better", "evidence", "eligible")):
        answer = "You can strengthen a future assessment by keeping consented financial evidence complete and by showing repayment behavior over time. More evidence does not guarantee approval; affordability and stress checks still apply."
    elif any(term in lowered for term in ("safe to learn", "starter")):
        answer = f"SAFE TO LEARN means NADI does not support the full request today, but may identify a smaller conservative starter exposure. The current recommended amount is INR {recommended or 0:,.0f}."
    else:
        answer = f"NADI currently shows {decision} with evidence confidence {confidence if confidence is not None else 'not available'}. Ask why the decision was made, what SAFE TO LEARN means, or what evidence can support a future assessment."
    return f"{answer} NADI's policy engine, not this assistant, makes lending decisions."


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
