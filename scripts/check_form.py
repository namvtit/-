"""Browser regression checks with configuration snapshots, not service E2E proof.

No successful generation is mocked. Real service testing lives in smoke.py.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://localhost:3000')
parser.add_argument('--browser-executable')
parser.add_argument('--material', type=Path, required=True, help='Real MP4 fixture for upload precedence check.')
args = parser.parse_args()

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True, executable_path=args.browser_executable)
    page = browser.new_page()
    baseline = page.request.get(args.url + '/api/config/public').json()
    snapshot = deepcopy(baseline)
    page.route('**/api/config/public', lambda route: route.fulfill(json=snapshot))
    # Every accidental generation fails the check; never invent a successful job.
    submissions = []
    def videos(route):
        if route.request.method == 'POST':
            submissions.append(route.request.post_data_json)
            route.fulfill(status=422, json={'detail': [{'loc': ['body', 'topic'], 'msg': 'Exact server validation error'}]})
        else:
            route.continue_()
    page.route('**/api/videos', videos)

    def load():
        page.goto(args.url)
        page.get_by_label('Topic/Prompt').fill('Forest')
        page.wait_for_function("!document.querySelector('.provider-connections').textContent.includes('Checking provider configuration')")
        return page.get_by_role('button', name='Generate video')

    snapshot['llm_configured'] = False
    snapshot['llm_connection'] = {'status': 'missing_configuration', 'detail': 'Missing: LLM_API_KEY.'}
    snapshot['default_footage_source'] = 'pixabay'
    for provider in snapshot['stock_providers']:
        provider['configured'] = provider['id'] == 'pixabay'
        provider['connection'] = {'status': 'unreachable', 'detail': 'Provider temporarily unreachable.'} if provider['configured'] else {
            'status': 'missing_configuration', 'detail': f"Missing: {provider['id'].upper()}_API_KEY."}
    generate = load()
    expect(generate).to_be_disabled()
    page.get_by_label('Narration Script').fill('A supplied narration.')
    expect(generate).to_be_enabled()  # No LLM needed; connection warning does not block.
    for source in ('pexels', 'coverr'):
        page.get_by_label('Footage source').select_option(source)
        expect(generate).to_be_disabled()
        expect(page.get_by_role('alert')).to_contain_text(f'{source.upper()}_API_KEY')
    page.get_by_label('Footage source').select_option('local')
    expect(generate).to_be_enabled()
    generate.click()
    expect(page.get_by_role('alert')).to_have_text('Local footage is selected; upload at least one MP4 clip or select a stock provider.')
    page.get_by_label('Local footage', exact=True).set_input_files(args.material)
    expect(page.locator('.material')).to_have_count(1)
    page.get_by_label('Footage source').select_option('coverr')
    expect(generate).to_be_enabled()  # Uploaded clips take precedence over missing Coverr.
    page.get_by_label('Narration Script').fill('   ')
    expect(generate).to_be_disabled()  # Whitespace script still needs the LLM.

    snapshot['llm_configured'] = True
    snapshot['llm_connection'] = {'status': 'unreachable', 'detail': 'LLM temporarily unreachable.'}
    generate = load()
    expect(generate).to_be_enabled()  # Both credentials exist despite connection warnings.
    page.get_by_label('Topic/Prompt').fill('   ')
    generate.click()
    expect(page.get_by_role('alert')).to_have_text('Topic/Prompt is required. Enter the idea for your video.')
    assert not submissions
    page.get_by_label('Topic/Prompt').fill('Forest')
    generate.click()
    expect(page.get_by_role('alert')).to_have_text('topic: Exact server validation error')
    assert len(submissions) == 1
    print(json.dumps({'result': 'PASS', 'checks': ['script bypasses missing LLM', 'only selected stock key required',
          'connection warnings do not disable Generate', 'local validation visible', 'uploaded clips override stock',
          'whitespace script needs LLM', 'blank topic validation visible', 'exact server validation detail visible']}))
    browser.close()
