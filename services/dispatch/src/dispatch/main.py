"""Dispatch's FastAPI app (SPEC.md §3.4)."""

from fastapi import FastAPI

from dispatch.routers import couriers, health, trips

app = FastAPI(title="Dinner Rush — dispatch")

app.include_router(health.router)
app.include_router(couriers.board_router)
app.include_router(couriers.courier_router)
app.include_router(trips.board_router)
app.include_router(trips.courier_router)
