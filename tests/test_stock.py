import httpx
import pytest
from apps.api.adapters.stock import StockConnections
from apps.api.config import Settings


async def test_missing_keys_are_named_without_network_calls():
    def handler(request):
        raise AssertionError('Unconfigured providers must not contact the network')
    settings = Settings(pexels_api_key='', pixabay_api_key='', coverr_api_key='')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        providers = await StockConnections(settings, client).providers()
    assert [provider.id for provider in providers] == ['pixabay', 'pexels', 'coverr']
    for provider in providers:
        assert not provider.configured
        assert provider.missing_keys == [f'{provider.id.upper()}_API_KEY']
        assert provider.connection.status == 'missing_configuration'


@pytest.mark.parametrize('source', ['pixabay', 'pexels', 'coverr'])
async def test_live_search_contract_and_cached_status(source):
    calls = []
    def handler(request):
        calls.append(request)
        if source == 'pixabay':
            assert request.url.params['key'] == 'secret'
        elif source == 'pexels':
            assert request.headers['Authorization'] == 'secret'
        else:
            assert request.headers['Authorization'] == 'Bearer secret'
        return httpx.Response(200, json={'videos' if source == 'pexels' else 'hits': []})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        stock = StockConnections(Settings(), client)
        provider = await stock.provider(source, 'secret')
        assert provider.configured and provider.connection.status == 'connected'
        assert 'secret' not in provider.model_dump_json()
        await stock.provider(source, 'secret')
        assert len(calls) == 1


@pytest.mark.parametrize('status', [401, 403, 429, 500])
async def test_failed_connection_is_not_missing_configuration(status):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(status, text='secret'))) as client:
        provider = await StockConnections(Settings(), client).provider('pixabay', 'secret')
    assert provider.configured and provider.missing_keys == []
    assert provider.connection.status == 'unreachable'
    assert f'HTTP {status}' in provider.connection.detail
    assert 'secret' not in provider.model_dump_json()


async def test_non_json_and_unexpected_responses_are_not_connected():
    for response in (httpx.Response(200, text='html'), httpx.Response(200, json={'error': 'secret'})):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: response)) as client:
            provider = await StockConnections(Settings(), client).provider('pixabay', 'secret')
        assert provider.connection.status == 'unreachable'
