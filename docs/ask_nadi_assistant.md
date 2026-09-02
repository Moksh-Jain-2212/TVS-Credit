# Ask NADI Assistant

Ask NADI is a borrower-facing explanation layer. It uses a LangChain `ChatPromptTemplate` with a de-identified, already-computed underwriting context.

## Boundary

Ask NADI can explain an existing decision, evidence confidence, SAFE_TO_LEARN, and possible future evidence. It cannot call the underwriting engine, change an application, promise approval, or create lending data.

Every answer displays this boundary:

```text
Ask NADI explains an existing assessment. It cannot approve, reject, change, or promise a loan decision.
```

## Generative mode

By default, Ask NADI returns a deterministic guided explanation. To enable the optional xAI/Grok-compatible generative response, set the backend environment value below and restart the server:

```text
GROK_EXPLANATION_ENABLED=true
```

It uses the existing backend-only `XAI_API_KEY`, `XAI_MODEL`, and `XAI_BASE_URL` configuration. Never expose those values to the browser or commit them to Git.

If the provider is unavailable, NADI automatically falls back to the guided explanation without affecting lending decisions.
