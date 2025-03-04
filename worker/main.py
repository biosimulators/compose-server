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
USE_WEBSOCKETS = os.getenv("USE_WEBSOCKETS", "True")

# singletons
db_connector = MongoConnector(connection_uri=MONGO_URI, database_id=DEFAULT_DB_NAME)
dispatcher = JobDispatcher(db_connector=db_connector)
app = FastAPI()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handles incoming WebSocket job requests from the Gateway."""
    await websocket.accept()
    logger.info("Worker WebSocket connection established.")

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            job_id = message.get("job_id")
            job_status = message.get("status")

            if job_status == "PENDING":
                logger.info(f"Received job {job_id} for processing.")

                # Run the job dispatcher logic
                response = await dispatcher.dispatch_composition(message)

                # Send response back to Gateway
                await websocket.send_text(json.dumps({"job_id": job_id, "status": "COMPLETE", "results": response}))
    except Exception as e:
        logger.error(f"Worker WebSocket error: {e}")
    finally:
        logger.info("Closing WebSocket connection.")


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
    asyncio.run(main()) if eval(USE_WEBSOCKETS) \
        else uvicorn.run(app, host="0.0.0.0", port=8001)
