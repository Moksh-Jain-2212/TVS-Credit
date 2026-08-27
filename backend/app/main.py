"""FastAPI entrypoint for the NADI backend."""

from fastapi import FastAPI


app = FastAPI(
    title="TVS NADI",
    description="Adaptive Credit Path Engine backend.",
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Return a simple service health response."""
    return {"status": "ok"}
