import pytest

from swarm.providers.factory import ProviderFactory


@pytest.fixture(autouse=True)
async def close_provider_clients_after_test():
    yield
    await ProviderFactory.close_cached()
