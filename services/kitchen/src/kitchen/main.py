"""Kitchen's FastAPI app (SPEC.md §3.3)."""

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from kitchen.observability import configure
from kitchen.routers import capacity, health, ovens, queue, tickets

configure()

app = FastAPI(title="Dinner Rush — kitchen")

FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()  # the JWKS fetch from front-of-house

app.include_router(health.router)
app.include_router(queue.router)
app.include_router(ovens.router)
app.include_router(ovens.admin_router)
app.include_router(capacity.router)
app.include_router(tickets.router)
