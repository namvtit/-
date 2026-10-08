import json
from uuid import uuid4
import httpx
import pytest
from apps.api.adapters.llm import LLMAdapter
from apps.api.adapters.moneyprinter import MoneyPrinterAdapter
from apps.api.config import Settings
from apps.api.db.jobs import JobStore, now
from apps.api.schemas.video import VideoInput
from apps.api.services.media import inspect_media, finalize
from apps.api.services.worker import JobWorker


def context(tmp_path, renderer, llm=None):
    settings = Settings(data_dir=tmp_path, poll_interval=.01)
    store = JobStore(tmp_path / 'jobs' / 'jobs.sqlite3')
    return store, JobWorker(settings, store, llm or LLMAdapter(settings, None), renderer)


async def test_restart_resumes_known_task_without_resubmission(tmp_path):
    class Renderer:
        async def task(self, task_id):
            return {'state': -1, 'failed_stage': 'audio', 'error': 'TTS unavailable'}
        async def submit(self, *args):
            raise AssertionError('Must never resubmit after API restart')
    store, worker = context(tmp_path, Renderer())
    job = store.create(VideoInput(topic='Recovery'))
    store.update(job['id'], status='RENDERING', upstream_task_id=str(uuid4()), submission_started_at=now())
    # New SQLite repository instance models a fresh backend process.
    worker.store = JobStore(store.path)
    await worker.process(worker.store.pending())
    result = store.get(job['id'])
    assert result['status'] == 'FAILED' and 'TTS unavailable' in result['error']


async def test_engine_restart_missing_task_is_failed(tmp_path):
    renderer = MoneyPrinterAdapter(Settings(data_dir=tmp_path), None)
    async def missing(_): return None
    renderer.task = missing
    store, worker = context(tmp_path, renderer)
    job = store.create(VideoInput(topic='Recovery'))
    job = store.update(job['id'], upstream_task_id=str(uuid4()), submission_started_at=now())
    await worker.process(job)
    assert store.get(job['id'])['status'] == 'FAILED'
    assert 'restart' in store.get(job['id'])['error']


async def test_ambiguous_submission_is_not_retried(tmp_path):
    store, worker = context(tmp_path, None)
    job = store.create(VideoInput(topic='Recovery'))
    job = store.update(job['id'], submission_started_at=now())
    await worker.process(job)
    assert store.get(job['id'])['status'] == 'FAILED'
    assert 'task ID' in store.get(job['id'])['error']


async def test_busy_renderer_keeps_next_job_queued(tmp_path):
    class Renderer:
        async def busy(self): return True
    store, worker = context(tmp_path, Renderer())
    job = store.create(VideoInput(topic='Next'))
    await worker.process(job)
    assert store.get(job['id'])['status'] == 'RECEIVED'
    assert store.get(job['id'])['submission_started_at'] is None


async def test_unreachable_renderer_does_not_submit(tmp_path):
    class Renderer:
        async def busy(self): raise httpx.ConnectError('offline')
    store, worker = context(tmp_path, Renderer())
    job = store.create(VideoInput(topic='Next'))
    await worker.process(job)
    assert store.get(job['id'])['status'] == 'RECEIVED'
    assert 'Waiting' in store.get(job['id'])['error']


async def test_invalid_completed_mp4_never_becomes_completed(tmp_path):
    renderer = MoneyPrinterAdapter(Settings(data_dir=tmp_path), None)
    task_id = str(uuid4())
    path = renderer.output_path(task_id)
    path.parent.mkdir(parents=True)
    path.write_bytes(b'corrupt mp4')
    async def task(_): return {'state': 1, 'videos': [f'/tasks/{task_id}/final-1.mp4']}
    renderer.task = task
    store, worker = context(tmp_path, renderer)
    job = store.create(VideoInput(topic='Corrupt'))
    job = store.update(job['id'], upstream_task_id=task_id, submission_started_at=now())
    with pytest.raises(ValueError):
        await worker.process(job)
    assert store.get(job['id'])['status'] != 'COMPLETED'


async def test_real_ffprobe_and_duration_conformance(tmp_path, real_clip):
    metadata = await inspect_media(real_clip)
    assert metadata.video_codec == 'h264' and metadata.audio_codec == 'aac'
    output = tmp_path / 'normalized.mp4'
    result = await finalize(real_clip, output, 30, '9:16')
    assert abs(result.duration - 30) < .2
    assert result.width == 540 and result.height == 960
    assert result.size_bytes == output.stat().st_size
    assert not output.with_suffix('.partial.mp4').exists()


async def test_engine_restart_recovers_only_valid_final_mp4(tmp_path, real_clip):
    renderer = MoneyPrinterAdapter(Settings(data_dir=tmp_path), None)
    async def missing(_): return None
    renderer.task = missing
    task_id = str(uuid4())
    path = renderer.output_path(task_id)
    path.parent.mkdir(parents=True)
    path.write_bytes(real_clip.read_bytes())
    store, worker = context(tmp_path, renderer)
    job = store.create(VideoInput(topic='Recovered final video', duration=30))
    job = store.update(job['id'], upstream_task_id=task_id, submission_started_at=now())
    await worker.process(job)
    result = store.get(job['id'])
    assert result['status'] == 'COMPLETED'
    assert abs(json.loads(result['metadata_json'])['duration'] - 30) < .2
    assert await inspect_media(__import__('pathlib').Path(result['final_mp4_path']))
