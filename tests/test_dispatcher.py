import json
import os
import asyncio

from worker.dispatch import JobDispatcher

TEST_DIR = os.path.dirname(os.path.abspath(__file__))


async def test_dispatch_composition():
    with open(os.path.join(TEST_DIR, "test_fixtures", "test_request.json")) as f:
        test_request = json.load(f)

    dispatcher = JobDispatcher()
    await dispatcher.dispatch_composition(test_request)


if __name__ == "__main__":
    asyncio.run(test_dispatch_composition())
