"""Read-only, real engine HTTP check; run inside api or with MONEYPRINTER_URL."""
import asyncio
import os
import httpx


async def main():
    base = os.getenv('MONEYPRINTER_URL', 'http://moneyprinter:8080').rstrip('/')
    async with httpx.AsyncClient(timeout=15) as client:
        ping = await client.get(f'{base}/ping')
        ping.raise_for_status()
        assert ping.json() == 'pong'
        tasks = await client.get(f'{base}/api/v1/tasks')
        tasks.raise_for_status()
        assert isinstance(tasks.json()['data']['tasks'], list)
        schema = await client.get(f'{base}/openapi.json')
        schema.raise_for_status()
        assert '/api/v1/videos' in schema.json()['paths']
    print('PASS: real MoneyPrinterTurbo ping, task list and generation API schema.')


asyncio.run(main())
