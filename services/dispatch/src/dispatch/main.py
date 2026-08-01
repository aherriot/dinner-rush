"""Dispatch's FastAPI app (SPEC.md §3.4)."""

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from dispatch.observability import configure
from dispatch.routers import couriers, health, trips

configure()

app = FastAPI(title="Dinner Rush — dispatch")

FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()  # the JWKS fetch from front-of-house

app.include_router(health.router)
app.include_router(couriers.board_router)
app.include_router(couriers.courier_router)
app.include_router(trips.board_router)
app.include_router(trips.courier_router)
