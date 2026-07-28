"""Kitchen's FastAPI app (SPEC.md §3.3)."""

from fastapi import FastAPI

from kitchen.routers import capacity, health, ovens, queue, tickets

app = FastAPI(title="Dinner Rush — kitchen")

app.include_router(health.router)
app.include_router(queue.router)
app.include_router(ovens.router)
app.include_router(ovens.admin_router)
app.include_router(capacity.router)
app.include_router(tickets.router)
