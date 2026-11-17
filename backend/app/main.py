import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models.database import engine, Base
from app.api.businesses import router as businesses_router
from app.api.forecasts import router as forecasts_router
from app.api.invoices import router as invoices_router
from app.api.closed_loop import router as closed_loop_router
from app.api.lender import router as lender_router
from app.api.statements import router as statements_router

# Ensure tables are initialized
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CashLoop API",
    description="Closed-Loop Cash-Flow Early-Warning System for Indian MSMEs",
    version="1.0.0"
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(businesses_router, prefix="/api")
app.include_router(forecasts_router, prefix="/api")
app.include_router(invoices_router, prefix="/api")
app.include_router(closed_loop_router, prefix="/api")
app.include_router(lender_router, prefix="/api")
app.include_router(statements_router, prefix="/api")

@app.get("/")
def root():
    return {
        "app": "CashLoop API",
        "status": "online",
        "docs_url": "/docs",
        "message": "Closed-Loop Cash-Flow Early-Warning Engine active"
    }

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}
