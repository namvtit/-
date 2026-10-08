"""Real public API E2E: upload (optional), submit, poll, preview, download, ffprobe.

No external call is mocked. Default mode needs LLM + a selected stock provider.
Use --script + --material to test real Edge TTS/rendering without those keys.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import httpx

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://localhost:3000')
parser.add_argument('--topic', default='Three ways to make a morning calmer')
parser.add_argument('--script', type=Path)
parser.add_argument('--material', type=Path, action='append', default=[])
parser.add_argument('--language', choices=['vi', 'en', 'zh'], default='vi')
parser.add_argument('--source', choices=['pixabay', 'pexels', 'coverr', 'local'], help='Defaults to a configured stock provider; uploaded clips take precedence.')
parser.add_argument('--output', type=Path, default=Path('/tmp/video-factory-smoke.mp4'))
parser.add_argument('--timeout', type=int, default=1800)
parser.add_argument('--restart-api', action='store_true', help='Restart only the API immediately after its upstream task ID is persisted.')
args = parser.parse_args()
with httpx.Client(base_url=args.url, timeout=120) as client:
    config = client.get('/api/config/public')
    config.raise_for_status()
    setup = config.json()
    source = args.source or ('local' if args.material else setup['default_footage_source'])
    if not args.script and not setup['llm_configured']:
        sys.exit('BLOCKED: set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in .env and run docker compose up -d --build.')
    if not args.material:
        if source == 'local':
            sys.exit('BLOCKED: Local source needs --material or select a stock provider.')
        provider = next(item for item in setup['stock_providers'] if item['id'] == source)
        if not provider['configured']:
            sys.exit(f"BLOCKED: set {', '.join(provider['missing_keys'])} or pass --material for real local footage.")
        print(f"Selected real stock provider: {provider['name']} ({provider['connection']['status']})", flush=True)
    keys = []
    for path in args.material:
        with path.open('rb') as file:
            upload = client.post('/api/materials', files={'file': (path.name, file, 'video/mp4')})
        upload.raise_for_status()
        keys.append(upload.json()['id'])
    response = client.post('/api/videos', json={
        'topic': args.topic, 'language': args.language, 'duration': 30, 'aspect_ratio': '9:16',
        'script': args.script.read_text() if args.script else None, 'local_materials': keys, 'footage_source': source,
    })
    response.raise_for_status()
    job_id = response.json()['id']
    print(f'Created real job: {job_id}', flush=True)
    deadline, restarted, previous = time.monotonic() + args.timeout, False, None
    while time.monotonic() < deadline:
        try:
            response = client.get(f'/api/videos/{job_id}')
            response.raise_for_status()
            job = response.json()
        except httpx.HTTPError:
            if restarted:
                time.sleep(3)
                continue
            raise
        if args.restart_api and not restarted and job['upstream_task_id']:
            subprocess.run(['docker', 'compose', 'restart', 'api'], check=True)
            restarted = True
            print('Restarted API with a persisted upstream task ID; verifying reconciliation.', flush=True)
        current = (job['status'], job['progress'], job['error'])
        if current != previous:
            print(f"{job['status']} {job['progress']}% {job['error'] or ''}", flush=True)
            previous = current
        if job['status'] == 'FAILED':
            sys.exit(f"FAILED real generation: {job['error']}")
        if job['status'] == 'COMPLETED':
            preview = client.get(job['preview_url'], headers={'Range': 'bytes=0-99'})
            assert preview.status_code == 206 and len(preview.content) == 100
            download = client.get(job['download_url'])
            download.raise_for_status()
            args.output.write_bytes(download.content)
            info = json.loads(subprocess.check_output([
                'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(args.output),
            ]))
            assert abs(float(info['format']['duration']) - 30) < .2
            assert {'video', 'audio'} <= {stream['codec_type'] for stream in info['streams']}
            video = next(stream for stream in info['streams'] if stream['codec_type'] == 'video')
            assert abs(video['width'] / video['height'] - 9 / 16) < .01
            if args.restart_api:
                assert restarted, 'Job completed too quickly to test restart.'
            print(f'PASS: real generation, preview Range, download, ffprobe{", and API restart recovery" if restarted else ""}: {args.output}')
            break
        time.sleep(3)
    else:
        sys.exit('FAILED: real job did not finish before smoke timeout; inspect its persisted state and renderer logs.')
