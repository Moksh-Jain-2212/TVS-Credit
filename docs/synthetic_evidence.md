# Segment-Aware Synthetic Evidence

NADI's GST and telecom **mock connectors** use a deterministic, parameterized generator for the local demo. They are not real integrations and must not be described as real borrower data.

## What is generated

- **GST / business:** twelve monthly aggregate turnover and filing-timeliness records. Small-merchant profiles have business-scale turnover, a gentle trend, and an October-November seasonal uplift.
- **Telecom:** aggregate recharge dates and amounts only. The generator never creates or stores calls, SMS, contacts, device identifiers, or location information.

The output depends on the application ID and borrower segment. Reconnecting the same source yields the same profile, so the demo is repeatable and a single borrower does not receive contradictory evidence across sources.

## Provenance

Every generated snapshot is marked:

```text
evidence_origin = PARAMETERIZED_SYNTHETIC_DEMO
generator_version = segment-synthetic-v1
```

This marker is displayed in the admin evidence view. It is deliberately separate from a future consented GST or telecom connector.

## Demo wording

> GST and telecom are parameterized, segment-aware demo evidence because public, consented individual-level Indian data is not available. NADI's normalisation, privacy controls, evidence confidence, and underwriting path are the same ones used by a future approved connector.

## PaySim boundary

PaySim can later be used only as a separately labelled benchmark for UPI-like aggregate transaction distributions. It is a synthetic mobile-money dataset, not Indian UPI data and not a source for individual lending decisions.
