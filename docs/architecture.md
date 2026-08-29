# Architecture

TVS NADI is a FastAPI and Next.js underwriting prototype for thin-file and new-to-credit borrowers.

```mermaid
flowchart LR
    Borrower[Borrower Portal] --> API[FastAPI API]
    Officer[Admin Portal] --> API
    API --> AppDB[(Application DB)]
    API --> PKDD[(PKDD Demo DB)]
    API --> Providers[Evidence Providers]
    Providers --> Context[Typed Underwriting Context]
    Context --> Risk[Risk Engine]
    Context --> Capacity[Capacity + Cash Flow]
    Context --> Confidence[Evidence Confidence]
    Risk --> Stress[Stress Simulator]
    Capacity --> Stress
    Confidence --> Ladder[Evidence Ladder]
    Stress --> Envelope[Repayment Envelope]
    Envelope --> Decision[NADI Decision Engine]
    Decision --> Explain[Deterministic + Optional Grok Explanation]
```

Core boundaries:

- Offline analytics and model training may use pandas heavily.
- Live platform underwriting builds explicit domain context before invoking engines.
- Grok/xAI is explanation-only and never makes credit decisions.
- Raw sensitive alternative-data payloads are not persisted in underwriting records.

