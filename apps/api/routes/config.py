import asyncio
from fastapi import APIRouter, Request
from apps.api.adapters.llm import public_base_url
from apps.api.schemas.video import PublicConfig

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    from fastapi import HTTPException
    worker = request.app.state.worker_task
    if worker.done():
        raise HTTPException(503, "Job worker is not running.")
    # Repository access also verifies persistence is available.
    request.app.state.store.list(1)
    return {"status": "ok"}


@router.get("/api/config/public", response_model=PublicConfig)
async def public_config(request: Request):
    state = request.app.state
    llm, renderer, providers = await asyncio.gather(state.llm.connection(), state.renderer.connection(), state.stock.providers())
    return PublicConfig(llm_base_url=public_base_url(state.settings.llm_api_base_url),
                        llm_model=state.settings.llm_model, llm_configured=state.settings.llm_configured,
                        llm_connection=llm, renderer_connection=renderer,
                        stock_configured=any(state.settings.stock_keys.values()), stock_providers=providers,
                        default_footage_source=state.settings.default_footage_source,
                        setup_issues=state.settings.setup_issues())
