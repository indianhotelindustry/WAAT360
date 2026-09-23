from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routers.approvals import router as approvals_router
from src.routers.bridge import router as bridge_router
from src.routers.companies import router as companies_router
from src.routers.dashboard import router as dashboard_router
from src.routers.documents import router as documents_router
from src.routers.proposals import router as proposals_router

app = FastAPI(title="WAAST360 Core API", version="0.1.0")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bridge_router)
app.include_router(companies_router)
app.include_router(dashboard_router)
app.include_router(documents_router)
app.include_router(proposals_router)
app.include_router(approvals_router)


@app.get("/")
def read_root():
    return {"status": "ok", "service": "WAAST360 Core API"}
