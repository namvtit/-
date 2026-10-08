from dataclasses import replace
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from apps.api.config import Settings
from apps.api.main import create_app
from apps.api.schemas.video import VideoInput


def test_missing_setup_is_explicit_and_no_job_created(tmp_path):
    settings = Settings(data_dir=tmp_path, llm_base_url="", llm_api_key="", llm_model="", pexels_api_key="")
    with TestClient(create_app(settings)) as client:
        assert client.get('/health').json() == {'status': 'ok'}
        response = client.post('/api/videos', json={'topic': 'A morning routine'})
        assert response.status_code == 503
        assert 'LLM_API_KEY' in response.json()['detail']
        assert client.get('/api/videos').json() == []


def test_validation_and_unknown_job(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        for params in ({'topic': ' '}, {'topic': 'hello', 'duration': 29},
                       {'topic': 'hello', 'duration': 61}, {'topic': 'hello', 'duration': '45'},
                       {'topic': 'hello', 'aspect_ratio': '1:1'},
                       {'topic': 'hello', 'local_materials': ['../../secret.mp4']}):
            assert client.post('/api/videos', json=params).status_code == 422
        assert client.get(f'/api/videos/{uuid4()}').status_code == 404
        assert client.get('/api/videos/not-an-id').status_code == 422
        assert client.get('/api/videos?limit=101').status_code == 422


def test_upload_real_media_and_no_keys_script_local_journey(tmp_path, real_clip):
    settings = Settings(data_dir=tmp_path, llm_api_key="", llm_model="", llm_base_url="", pexels_api_key="")
    with TestClient(create_app(settings)) as client:
        with real_clip.open('rb') as file:
            response = client.post('/api/materials', files={'file': ('../../clip.mp4', file, 'video/mp4')})
        assert response.status_code == 201
        material = response.json()
        assert material['name'] == 'clip.mp4'
        assert (tmp_path / 'inputs' / material['id']).is_file()
        job = client.post('/api/videos', json={'topic': 'Local video', 'script': 'A supplied narration.',
                                              'local_materials': [material['id']]}).json()
        assert job['input']['language'] == 'vi'
        assert job['id'] != material['id']
        assert job['preview_url'] is None
        assert client.get(f"/api/videos/{job['id']}/download").status_code == 409
        assert client.get(f"/api/videos/{job['id']}").status_code == 200


def test_invalid_upload_rejected_and_cleaned(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        assert client.post('/api/materials', files={'file': ('clip.mp4', b'not a video')}).status_code == 422
        assert client.post('/api/materials', files={'file': ('script.py', b'print(1)')}).status_code == 422
        assert list((tmp_path / 'inputs').iterdir()) == []


def test_download_range_and_missing_completed_output(tmp_path, real_clip):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        store = client.app.state.store
        row = store.create(VideoInput(topic='Download test'))
        dest = tmp_path / 'outputs' / 'video.mp4'
        dest.write_bytes(real_clip.read_bytes())
        # This tests HTTP serving; completion itself is validated in worker tests.
        store.update(row['id'], status='COMPLETED', final_mp4_path=str(dest))
        url = f"/api/videos/{row['id']}/preview"
        response = client.get(url, headers={'Range': 'bytes=0-99'})
        assert response.status_code == 206
        assert len(response.content) == 100
        response = client.get(f"/api/videos/{row['id']}/download")
        assert response.content == real_clip.read_bytes()
        assert 'attachment' in response.headers['content-disposition']
        dest.unlink()
        assert client.get(url).status_code == 410


def test_second_dispatcher_cannot_start(tmp_path):
    settings = Settings(data_dir=tmp_path)
    with TestClient(create_app(settings)):
        with pytest.raises(RuntimeError, match='Another API worker'):
            with TestClient(create_app(settings)):
                pass


@pytest.mark.parametrize('source', ['pixabay', 'pexels', 'coverr'])
def test_supplied_script_and_selected_stock_need_no_llm(tmp_path, source):
    settings = Settings(data_dir=tmp_path, llm_base_url='', llm_api_key='', llm_model='',
                        pexels_api_key='', pixabay_api_key='', coverr_api_key='')
    settings = replace(settings, **{f'{source}_api_key': 'configured'})
    with TestClient(create_app(settings)) as client:
        response = client.post('/api/videos', json={'topic': 'Forest', 'script': 'Trees provide shade.', 'footage_source': source})
        assert response.status_code == 202
        assert response.json()['input']['footage_source'] == source
        # Empty/whitespace narration still requires the LLM.
        response = client.post('/api/videos', json={'topic': 'Forest', 'script': '  ', 'footage_source': source})
        assert response.status_code == 503
        assert 'LLM_API_KEY' in response.json()['detail']
        assert f'{source.upper()}_API_KEY' not in response.json()['detail']


def test_missing_selected_key_and_empty_local_are_exact_errors(tmp_path):
    settings = Settings(data_dir=tmp_path, llm_base_url='', llm_api_key='', llm_model='',
                        pexels_api_key='', pixabay_api_key='configured', coverr_api_key='')
    with TestClient(create_app(settings)) as client:
        response = client.post('/api/videos', json={'topic': 'Forest', 'script': 'Trees.', 'footage_source': 'pexels'})
        assert response.status_code == 503
        assert response.json()['detail'] == 'Set PEXELS_API_KEY in .env or upload local MP4 clips.'
        response = client.post('/api/videos', json={'topic': 'Forest', 'script': 'Trees.', 'footage_source': 'local'})
        assert response.status_code == 422
        assert response.json()['detail'] == 'Local footage is selected; upload at least one MP4 clip or select a stock provider.'
        assert client.get('/api/videos').json() == []


def test_topic_and_local_with_empty_script_require_only_llm(tmp_path, real_clip):
    settings = Settings(data_dir=tmp_path, llm_base_url='https://provider.test/v1', llm_api_key='configured', llm_model='model',
                        pexels_api_key='', pixabay_api_key='', coverr_api_key='')
    with TestClient(create_app(settings)) as client:
        with real_clip.open('rb') as file:
            material = client.post('/api/materials', files={'file': ('clip.mp4', file, 'video/mp4')}).json()
        response = client.post('/api/videos', json={'topic': 'Forest', 'footage_source': 'coverr', 'local_materials': [material['id']]})
        assert response.status_code == 202


def test_unknown_stock_provider_rejected(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        response = client.post('/api/videos', json={'topic': 'Forest', 'footage_source': 'unknown'})
        assert response.status_code == 422
        assert response.json()['detail'][0]['loc'] == ['body', 'footage_source']
