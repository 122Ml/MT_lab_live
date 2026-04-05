import asyncio

from fastapi import APIRouter, Depends, Request

from app.core.config import Settings, get_settings
from app.schemas.translation import (
    BatchTranslateRequest,
    EngineResult,
    EvaluateRequest,
    EvaluateResponse,
    TestCaseItem,
    TranslateRequest,
    TranslateResponse,
)
from app.services.engine_manager import EngineManager
from app.services.evaluator import EvaluatorService
from app.services.test_case_service import TestCaseService

router = APIRouter(prefix="/api/v1", tags=["translation"])


def get_engine_manager(request: Request, settings: Settings = Depends(get_settings)) -> EngineManager:
    manager = getattr(request.app.state, "engine_manager", None)
    if manager is None:
        manager = EngineManager(settings)
        request.app.state.engine_manager = manager
    return manager


def get_evaluator(request: Request) -> EvaluatorService:
    evaluator = getattr(request.app.state, "evaluator", None)
    if evaluator is None:
        evaluator = EvaluatorService()
        request.app.state.evaluator = evaluator
    return evaluator


def get_test_case_service(request: Request) -> TestCaseService:
    service = getattr(request.app.state, "test_case_service", None)
    if service is None:
        service = TestCaseService()
        request.app.state.test_case_service = service
    return service


def apply_metrics(
    results: list[EngineResult],
    reference: str | None,
    evaluator: EvaluatorService,
) -> list[EngineResult]:
    if not reference:
        return results

    enriched: list[EngineResult] = []
    for result in results:
        if result.ready:
            bleu, chrf = evaluator.evaluate(result.translation, reference)
            enriched.append(result.model_copy(update={"bleu": bleu, "chrf": chrf}))
        else:
            enriched.append(result)
    return enriched


@router.get("/engines")
async def engines(manager: EngineManager = Depends(get_engine_manager)) -> dict[str, dict[str, str | bool]]:
    return manager.status()


@router.post("/translate", response_model=TranslateResponse)
async def translate(
    payload: TranslateRequest,
    manager: EngineManager = Depends(get_engine_manager),
    evaluator: EvaluatorService = Depends(get_evaluator),
) -> TranslateResponse:
    raw_results = await manager.translate_with_selected(
        text=payload.text,
        src_lang=payload.src_lang,
        tgt_lang=payload.tgt_lang,
        selected=payload.engines,
    )
    results = apply_metrics(raw_results, payload.reference, evaluator)
    return TranslateResponse(
        text=payload.text,
        src_lang=payload.src_lang,
        tgt_lang=payload.tgt_lang,
        reference=payload.reference,
        results=results,
    )


@router.post("/batch_translate")
async def batch_translate(
    payload: BatchTranslateRequest,
    manager: EngineManager = Depends(get_engine_manager),
    evaluator: EvaluatorService = Depends(get_evaluator),
) -> dict[str, list[TranslateResponse]]:
    references = payload.references or [None] * len(payload.texts)
    normalized_references = [references[index] if index < len(references) else None for index in range(len(payload.texts))]

    async def run_single(index: int, text: str) -> TranslateResponse:
        reference = references[index] if index < len(references) else None
        raw_results = await manager.translate_with_selected(
            text=text,
            src_lang=payload.src_lang,
            tgt_lang=payload.tgt_lang,
            selected=payload.engines,
        )
        results = apply_metrics(raw_results, reference, evaluator)
        return TranslateResponse(
            text=text,
            src_lang=payload.src_lang,
            tgt_lang=payload.tgt_lang,
            reference=reference,
            results=results,
        )

    tasks = [run_single(index, text) for index, text in enumerate(payload.texts)]
    items = await asyncio.gather(*tasks)

    items = [
        item.model_copy(update={"reference": normalized_references[index]})
        for index, item in enumerate(items)
    ]
    return {"items": items}


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(payload: EvaluateRequest, evaluator: EvaluatorService = Depends(get_evaluator)) -> EvaluateResponse:
    bleu, chrf = evaluator.evaluate(payload.candidate, payload.reference)
    return EvaluateResponse(bleu=bleu, chrf=chrf)


@router.get("/test_cases", response_model=list[TestCaseItem])
async def list_test_cases(service: TestCaseService = Depends(get_test_case_service)) -> list[TestCaseItem]:
    return service.list_cases()
