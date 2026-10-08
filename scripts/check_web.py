"""Optional real browser check. Requires playwright + installed Chromium.

Run after a smoke job to verify completed-video playback and browser download:
  uv pip install --python .venv/bin/python playwright
  .venv/bin/python -m playwright install chromium
  .venv/bin/python scripts/check_web.py
"""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://localhost:3000')
parser.add_argument('--browser-executable')
parser.add_argument('--artifacts', type=Path, default=Path('/tmp/video-factory-browser'))
args = parser.parse_args()
args.artifacts.mkdir(parents=True, exist_ok=True)
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True, executable_path=args.browser_executable)
    page = browser.new_page(viewport={'width': 1440, 'height': 1050})
    errors, external = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: external.append(request.url)
            if not request.url.startswith(args.url.rstrip('/') + '/') else None)
    page.goto(args.url)
    page.get_by_text('A topic. A finished video.').wait_for()
    page.get_by_label('Topic/Prompt').fill('Three habits for a calmer morning')
    assert page.get_by_label('Narration Script').is_visible()
    assert page.get_by_label('Narration Script').input_value() == ''
    source = page.get_by_label('Footage source')
    assert source.locator('option').all_text_contents() == ['Pixabay', 'Pexels', 'Coverr', 'Local']
    page.wait_for_function("document.querySelector('.sidebar-bottom').textContent.includes('Renderer connected')")
    setup = page.request.get(args.url + '/api/config/public').json()
    assert source.input_value() == setup['default_footage_source']
    if setup['llm_configured'] and setup['stock_configured']:
        assert page.get_by_role('button', name='Generate video').is_enabled()
    source.select_option('local')
    assert page.get_by_label('Local footage', exact=True).is_visible()
    page.get_by_label('Narration Script').fill('A supplied script.')
    assert page.get_by_role('button', name='Generate video').is_enabled()
    page.get_by_role('button', name='Generate video').click()
    assert page.get_by_role('alert').filter(has_text='Local footage is selected; upload at least one MP4 clip or select a stock provider.').is_visible()
    source.select_option(setup['default_footage_source'])
    page.get_by_label('Narration Script').fill('')
    page.screenshot(path=str(args.artifacts / 'dashboard.png'), full_page=True)
    page.get_by_role('button', name='Settings', exact=True).click()
    page.get_by_role('heading', name='AI script provider').wait_for()
    assert page.get_by_text('MoneyPrinterTurbo', exact=True).is_visible()
    page.get_by_role('button', name='Your videos', exact=True).click()
    page.get_by_role('heading', name='Your videos', exact=True).wait_for()
    completed = page.locator('.job-card', has=page.locator('video')).first
    checks = ['distinct topic/script inputs', 'four footage sources', 'configured default source', 'explicit empty-local validation', 'dashboard', 'settings', 'jobs', 'responsive layout']
    # A completed real smoke job enables playback/download verification.
    if completed.count():
        video = completed.locator('video')
        video.evaluate("video => { video.muted = true; return video.play(); }")
        page.wait_for_function("Array.from(document.querySelectorAll('video')).some(v => v.currentTime > 0)")
        assert video.evaluate('video => video.videoWidth > 0 && video.duration > 0')
        video.evaluate('video => video.pause()')
        with page.expect_download() as result:
            completed.get_by_role('link', name='Download MP4').click()
        result.value.save_as(args.artifacts / 'browser-download.mp4')
        checks += ['real video playback', 'real browser MP4 download']
    page.screenshot(path=str(args.artifacts / 'jobs.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    page.get_by_role('button', name='Create video', exact=True).click()
    page.screenshot(path=str(args.artifacts / 'mobile.png'), full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    assert not errors, errors
    assert not external, external
    checks += ['no JavaScript errors', 'browser requests only this application']
    print(json.dumps({'result': 'PASS', 'checks': checks}))
    browser.close()
