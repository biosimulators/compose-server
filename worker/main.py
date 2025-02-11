import os
import asyncio
import logging

from dotenv import load_dotenv

from shared.database import MongoConnector
from shared.environment import ENV_PATH, DEFAULT_DB_NAME
from shared.log_config import setup_logging

from worker.dispatch import JobDispatcher


load_dotenv(ENV_PATH)  # NOTE: create an env config at this filepath if dev


# logging
logger = setup_logging(__file__)

# constraints
TIMEOUT = 30
MAX_RETRIES = 30
MONGO_URI = os.getenv("MONGO_URI")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# singletons
db_connector = MongoConnector(connection_uri=MONGO_URI, database_id=DEFAULT_DB_NAME)
dispatcher = JobDispatcher(db_connector=db_connector)


async def main(max_retries=MAX_RETRIES):
    n_retries = 0
    while True:
        # no job has come in a while
        if n_retries == MAX_RETRIES:
            await asyncio.sleep(TIMEOUT)  # TODO: adjust this for client polling as needed
        await dispatcher.run()
        await asyncio.sleep(10)
        n_retries += 1


if __name__ == "__main__":
    asyncio.run(main())
