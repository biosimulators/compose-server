""""
Alex Patrie 1/6/2025

NOTE: This workflow is run by the microservices architecture and offloads ALL simulation logic to Biosimulator Processes!

The general workflow should be:

1. gateway: client uploads JSON spec file
2. gateway: gateway stores the JSON spec as a job in mongo
3. gateway: spec is returned to client as confirmation
4. worker: check for pending statuses in mongo collection (single)
5. worker: get simulators/deps from #4 TODO: somehow do this!!
6. worker: dynamic install #5
7. worker: change job status in DB to IN_PROGRESS
8. worker: run composition with pbg.Composite() and gather_results()
9. worker: change job status in DB to COMPLETE
10. worker: update job document ['results'] field with #8's data
11. worker: perhaps emit an event?
"""


import asyncio
import json
import subprocess
import tempfile
import os
from typing import Any, Mapping, List

from process_bigraph import Composite

from shared.database import MongoConnector
from shared.dynamic_env import install_request_dependencies, create_dynamic_environment
from shared.log_config import setup_logging


logger = setup_logging(__file__)


class CompositionWorker(object):
    def __init__(self):
        self.results = None
        self.output_state = None

    @staticmethod
    async def install_simulators(job: Mapping[str, Any]):
        simulators = job["simulators"]
        job_id = job["job_id"]
        return install_request_dependencies(job_id=job_id, simulators=simulators)

    async def write_update(self, db_connector, job_id, **fields):
        return await db_connector.update_job(job_id=job_id, **fields)

    async def dispatch(self, job: Mapping[str, Any], db_connector: MongoConnector = None):
        # TODO: add try blocks for each section
        job_status = job["status"]
        if job_status.lower() == "pending":
            # 3. install simulators required
            # create_dynamic_environment(job)
            # await self.install_simulators(job)

            # 4. change job status to IN_PROGRESS
            job_id = job["job_id"]
            # await self.write_update(db_connector=db_connector, job_id=job_id, status="IN_PROGRESS")
            # await db_connector.update_job(job_id=job_id, status="IN_PROGRESS")

            input_state = job["spec"]
            duration = job.get("duration", 1)
            self.generate_results(input_state, duration)

            # # 5. from bsp import app_registrar.core
            # bsp = __import__("bsp")
            # core = bsp.app_registrar.core
            # # 6. create Composite() with core and job["job_spec"]
            # composition = Composite(
            #     config={"state": job["spec"]},
            #     core=core
            # )
            # # 7. run composition with instance from #6 for specified duration (default 1)
            # dur = job.get("duration", 1)
            # composition.run(dur)
            # # 8. get composition results indexed from ram-emitter
            # results = composition.gather_results()[("emitter",)]
            # self.results = results
            # # 9. update job in DB ['results'] to Composite().gather_results() AND change status to COMPLETE
            # # await self.write_update(db_connector=db_connector, job_id=job_id, status="COMPLETE", results=results)
            # # await db_connector.update_job(job_id=job_id, status="COMPLETE", results=results)
            # # 10. add new result state in db within result_states collection!
            # temp_dir = tempfile.mkdtemp()
            # temp_fname = f"{job}.state.json"
            # composition.save(filename=temp_fname, outdir=temp_dir)
            # temp_path = os.path.join(temp_dir, temp_fname)
            # with open(temp_path, 'r') as f:
            #     current_data = json.load(f)
            # self.output_state = current_data

            # await db_connector.write(
            #     collection_name="result_states",
            #     job_id=job_id,
            #     data=current_data,
            #     last_updated=db_connector.timestamp()
            # )

            # 11. remove composite state file artifact
            # os.remove(temp_path) if os.path.exists(temp_path) else None

    def generate_results(self, input_state: Mapping[str, Any], duration: int):
        print('Got input state: ')
        from process_bigraph import pp
        pp(input_state)
        from bsp import app_registrar

        print(f'Registered processes: {app_registrar.registered_addresses}')

        composition = Composite(
            config={"state": input_state},
            core=app_registrar.core
        )
        # # composition.run(duration)
        # results = composition.gather_results()[("emitter",)]
        # self.results = results
        # # 10. add new result state in db within result_states collection!
        # temp_dir = tempfile.mkdtemp()
        # temp_fname = f"temp.state.json"
        # composition.save(filename=temp_fname, outdir=temp_dir)
        # temp_path = os.path.join(temp_dir, temp_fname)
        # with open(temp_path, 'r') as f:
        #     current_data = json.load(f)
        # self.output_state = current_data
        # os.remove(temp_path) if os.path.exists(temp_path) else None
        # return None






