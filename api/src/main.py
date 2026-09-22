from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routers.bridge import router as bridge_router
from src.routers.companies import router as companies_router

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


@app.get("/")
def read_root():
    return {"status": "ok", "service": "WAAST360 Core API"}
