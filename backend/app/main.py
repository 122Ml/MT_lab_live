from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.services.engine_manager import EngineManager
from app.services.evaluator import EvaluatorService
from app.services.test_case_service import TestCaseService

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.engine_manager = EngineManager(settings)
    app.state.evaluator = EvaluatorService()
    app.state.test_case_service = TestCaseService()
    yield


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str | dict[str, dict[str, str | bool]]]:
    engine_manager: EngineManager = app.state.engine_manager
    return {
        "status": "ok",
        "env": settings.app_env,
        "engines": engine_manager.status(),
    }


app.include_router(api_router)
