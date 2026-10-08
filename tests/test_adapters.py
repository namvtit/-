from uuid import uuid4
import httpx
import pytest
from apps.api.adapters.interfaces import VideoPlan
from apps.api.adapters.llm import LLMAdapter, public_base_url
from apps.api.adapters.moneyprinter import MoneyPrinterAdapter
from apps.api.config import Settings
from apps.api.schemas.video import VideoInput


async def test_renderer_http_contract_and_local_inputs(tmp_path):
    import json
    task_id = str(uuid4())
    def handler(request):
        payload = json.loads(request.content)
        assert request.url.path == '/api/v1/videos'
        assert payload['video_source'] == 'local'
        assert payload['video_script'] == 'Supplied script.'
        assert payload['voice_name'] == 'vi-VN-HoaiMyNeural-Female'
        assert payload['font_name'] == 'BeVietnamPro-Medium.ttf'
        assert payload['video_count'] == 1 and payload['n_threads'] == 2
        assert payload['video_materials'][0]['url'].endswith('.mp4')
        return httpx.Response(200, json={'data': {'task_id': task_id}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        renderer = MoneyPrinterAdapter(Settings(data_dir=tmp_path), client)
        assert await renderer.submit(VideoInput(topic='Test', local_materials=[f'{uuid4()}.mp4']),
                                     VideoPlan(script='Supplied script.', search_terms=['nature'])) == task_id


async def test_renderer_status_contract():
    def handler(request):
        if request.url.path.endswith('/missing'):
            return httpx.Response(404)
        return httpx.Response(200, json={'data': {'tasks': [{'state': 4}]}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        renderer = MoneyPrinterAdapter(Settings(), client)
        assert await renderer.task('missing') is None
        assert await renderer.busy()


def test_output_cannot_escape_task_directory(tmp_path):
    renderer = MoneyPrinterAdapter(Settings(data_dir=tmp_path), None)
    task_id = str(uuid4())
    assert renderer.output_path(task_id).name == 'final-1.mp4'
    assert renderer.output_path(task_id, f'/tasks/{task_id}/final-1.mp4').parent.name == task_id
    for uri in (f'/tasks/{task_id}/../../secret.mp4', f'/tasks/{task_id}/%2e%2e/secret.mp4', '/tasks/other/final-1.mp4'):
        with pytest.raises(ValueError):
            renderer.output_path(task_id, uri)


async def test_llm_bad_credentials_do_not_leak_provider_body():
    settings = Settings(llm_base_url='https://provider.test/v1', llm_api_key='top-secret', llm_model='model')
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(401, text='top-secret'))) as client:
        with pytest.raises(ValueError, match='HTTP 401') as error:
            await LLMAdapter(settings, client).generate(VideoInput(topic='Test'))
        assert 'top-secret' not in str(error.value)


async def test_llm_generates_json_plan_from_topic():
    import json
    settings = Settings(llm_base_url='https://provider.test/v1', llm_api_key='key', llm_model='model')
    def handler(request):
        payload = json.loads(request.content)
        assert payload['model'] == 'model'
        assert '30-second video' in payload['messages'][0]['content']
        return httpx.Response(200, json={'choices': [{'message': {'content': '```json\n{"script":"changed", "search_terms":["forest"]}\n```'}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        plan = await LLMAdapter(settings, client).generate(VideoInput(topic='Trees', duration=30))
        assert plan.script == 'changed' and plan.search_terms == ['forest']


@pytest.mark.parametrize('materials', [[], [f'{uuid4()}.mp4']])
async def test_supplied_script_does_not_call_llm(materials):
    class NoNetwork:
        async def post(self, *args, **kwargs):
            raise AssertionError('No LLM request allowed')
    plan = await LLMAdapter(Settings(), NoNetwork()).generate(
        VideoInput(topic='Test', script='Original', local_materials=materials))
    assert plan.script == 'Original'


@pytest.mark.parametrize('source', ['pixabay', 'pexels', 'coverr'])
async def test_renderer_uses_selected_stock_provider(source):
    import json
    task_id = str(uuid4())
    def handler(request):
        payload = json.loads(request.content)
        assert payload['video_source'] == source
        assert payload['video_materials'] == []
        assert payload['video_terms'] == ['forest']
        return httpx.Response(200, json={'data': {'task_id': task_id}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await MoneyPrinterAdapter(Settings(), client).submit(
            VideoInput(topic='Forest', footage_source=source), VideoPlan(script='Trees.', search_terms=['forest'])) == task_id


def test_public_url_scrubs_secrets():
    assert public_base_url('https://user:secret@provider.test/v1?api_key=secret#secret') == 'https://provider.test/v1'


@pytest.mark.parametrize('base, expected', [
    ('https://gateway.test', 'https://gateway.test/v1'),
    ('https://gateway.test/', 'https://gateway.test/v1'),
    ('https://gateway.test/v1', 'https://gateway.test/v1'),
    ('https://gateway.test/api/paas/v4', 'https://gateway.test/api/paas/v4'),
    ('', ''),
])
def test_gateway_root_normalized_without_changing_explicit_paths(base, expected):
    assert Settings(llm_base_url=base).llm_api_base_url == expected
