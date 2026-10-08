from pathlib import Path
from uuid import UUID, uuid4
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from apps.api.schemas.video import Job, Material, Status, VideoInput
from apps.api.services.media import inspect_media

router = APIRouter(prefix="/api")
MAX_UPLOAD = 100 * 1024 * 1024


def find_job(request: Request, job_id: UUID) -> dict:
    row = request.app.state.store.get(str(job_id))
    if row is None:
        raise HTTPException(404, "Job not found.")
    return row


@router.post("/videos", response_model=Job, status_code=202)
async def create_video(params: VideoInput, request: Request):
    settings = request.app.state.settings
    if params.effective_source == "local" and not params.local_materials:
        raise HTTPException(422, "Local footage is selected; upload at least one MP4 clip or select a stock provider.")
    missing = settings.required_configuration(params)
    if missing:
        raise HTTPException(503, " ".join(missing))
    for key in params.local_materials:
        if not (settings.data_dir / "inputs" / key).is_file():
            raise HTTPException(422, f"Local material {key} does not exist; upload it first.")
    store = request.app.state.store
    return store.public(store.create(params))


@router.get("/videos", response_model=list[Job])
async def list_videos(request: Request, limit: int = Query(50, ge=1, le=100)):
    store = request.app.state.store
    return [store.public(row) for row in store.list(limit)]


@router.get("/videos/{job_id}", response_model=Job)
async def get_video(job_id: UUID, request: Request):
    return request.app.state.store.public(find_job(request, job_id))


def completed_file(request: Request, job_id: UUID) -> Path:
    row = find_job(request, job_id)
    if row["status"] != Status.COMPLETED.value or not row["final_mp4_path"]:
        raise HTTPException(409, "Video is not completed.")
    path = Path(row["final_mp4_path"]).resolve()
    root = (request.app.state.settings.data_dir / "outputs").resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(410, "Completed video is missing from persistent storage.")
    return path


@router.get("/videos/{job_id}/download")
async def download_video(job_id: UUID, request: Request):
    return FileResponse(completed_file(request, job_id), media_type="video/mp4", filename=f"video-{job_id}.mp4")


@router.get("/videos/{job_id}/preview")
async def preview_video(job_id: UUID, request: Request):
    # Starlette FileResponse supports Range requests, including video seeking.
    return FileResponse(completed_file(request, job_id), media_type="video/mp4")


@router.post("/materials", response_model=Material, status_code=201)
async def upload_material(request: Request, file: UploadFile = File(...)):
    if not file.filename or Path(file.filename).suffix.lower() != ".mp4":
        raise HTTPException(422, "Upload MP4 video clips, up to 100 MB each.")
    key = f"{uuid4()}.mp4"
    root = request.app.state.settings.data_dir / "inputs"
    temp, destination = root / f".{key}.upload", root / key
    size = 0
    try:
        with temp.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, "Material exceeds the 100 MB limit.")
                output.write(chunk)
        try:
            metadata = await inspect_media(temp, require_audio=False)
            if min(metadata.width, metadata.height) < 480:
                raise ValueError("Clips must be at least 480 pixels in both dimensions.")
        except (ValueError, TimeoutError) as exc:
            raise HTTPException(422, str(exc)) from exc
        temp.replace(destination)
        return Material(id=key, name=Path(file.filename.replace("\\", "/")).name, size_bytes=size)
    finally:
        temp.unlink(missing_ok=True)
        await file.close()
