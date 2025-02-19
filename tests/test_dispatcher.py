import json
import os
import asyncio

import pytest
from process_bigraph import Composite

from worker.dispatch import JobDispatcher

# TEST_DIR = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture
def test_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


@pytest.fixture
@pytest.mark.usefixtures("test_dir")
def payload(test_dir: str) -> dict:
    with open(os.path.join(test_dir, "test_fixtures", "test_membrane_request2.json")) as f:
        test_request = json.load(f)
    return test_request


@pytest.mark.usefixtures('payload')
class TestDispatcher:
    def setup_method(self):
        self.dispatcher = JobDispatcher()

    def test_generate_composition(self, payload: dict):
        composition = self.dispatcher.generate_composite(payload)
        assert composition is not None
        print(f'Got the composition state:\n{composition.state}')


def get_test_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def get_payload() -> dict:
    test_dir = get_test_dir()
    with open(os.path.join(test_dir, "test_fixtures", "test_membrane_request2.json")) as f:
        test_request = json.load(f)
    return test_request


async def test_generate_composition():
    dispatcher = JobDispatcher()
    payload = get_payload()
    await dispatcher.dispatch_composition(payload)
    # assert composition is not None
    # print(f'Got the composition state:\n{composition.state}')


asyncio.run(test_generate_composition())

# @pytest.mark.asyncio
# async def test_dispatch_composition():
#     dispatcher = JobDispatcher()
#     await dispatcher.dispatch_composition(test_request)

