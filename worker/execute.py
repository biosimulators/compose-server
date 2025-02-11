import asyncio
import sys
import tempfile
import json
import os

job = sys.argv[1]
job_id = sys.argv[2]
job = json.loads(job)
mongo_uri = sys.argv[3]
local_connection = sys.argv[4]


async def run():
    pass


if __name__ == "__main__":
    asyncio.run(run())
