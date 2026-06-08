from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import analytics, overview, produce, reconciliation, transactions

app = FastAPI(
    title="AML Dashboard API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(overview.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(reconciliation.router, prefix="/api")
app.include_router(produce.router, prefix="/api")


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok"}
