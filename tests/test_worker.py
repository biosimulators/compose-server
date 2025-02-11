import asyncio
import os
import json

from dotenv import load_dotenv
from process_bigraph import pp

from shared.database import MongoConnector
from shared.environment import DEFAULT_DB_NAME, ENV_PATH, PROJECT_ROOT_PATH
from shared.dynamic_env import create_dynamic_environment
from shared.log_config import setup_logging
from worker.workers.composition import CompositionWorker


load_dotenv(ENV_PATH)

MONGO_URI = os.getenv('MONGO_URI')
GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
BUCKET_NAME = os.getenv('BUCKET_NAME')
DB_NAME = os.getenv('DB_NAME')
TEST_REQUEST_PATH = os.path.join(PROJECT_ROOT_PATH, 'tests', 'test_fixtures', 'membrane_composite.json')

logger = setup_logging(__file__)


def test_membrane_job():
    worker = CompositionWorker()
    import json

    with open(TEST_REQUEST_PATH, 'r') as f:
        state = json.load(f)

    worker.generate_results(input_state=state, duration=3)
    # print(f'Emitter results:\n')
    # pp(worker.results)
    # print(f'Composition state:\n')
    # pp(worker.output_state)


if __name__ == '__main__':
    test_membrane_job()


