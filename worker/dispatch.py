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
import tempfile

import os
from dataclasses import dataclass
from typing import Any, Mapping, List

import bsp
from process_bigraph import Composite
from bsp import app_registrar
from bsp.processes.simple_membrane_process import SimpleMembraneProcess

from shared.io import download_file_from_bucket
from shared.database import MongoConnector
from shared.environment import DEFAULT_BUCKET_NAME
from shared.log_config import setup_logging
from worker.sim_runs.runs import RunsWorker
from shared.utils import handle_exception
from shared.data_model import BaseClass, StateData


logger = setup_logging(__file__)


# class CompositionState(dict):
#     """That which is exported by Composite.save()"""
#     def __new__(cls, *args, **kwargs):
#         return super(CompositionState, cls).__new__(cls, *args, **kwargs)
#
#
# class ResultData(dict):
#     """That which is exported by Composite.gather_results()"""
#     def __new__(cls, *args, **kwargs):
#         return super(ResultData, cls).__new__(cls, *args, **kwargs)


@dataclass
class CompositionState(StateData):
    pass


@dataclass
class ResultData(StateData):
    pass


@dataclass
class ServerResponse:
    results: ResultData
    state: CompositionState


class JobDispatcher(object):
    def __init__(self,
                 db_connector: MongoConnector = None,
                 timeout: int = 5):
        """
        :param db_connector: (`shared.database.MongoConnector`) database connector singleton instantiated with mongo uri.
        :param timeout: number of minutes for timeout. Default is 5 minutes
        """
        self.db_connector = db_connector
        self.timeout = timeout * 60

    @property
    def db_io(self) -> bool:
        return self.db_connector is not None

    async def run(self, limit: int = 5, wait: int = 5):
        if self.db_io:
            i = 0
            while i < limit:
                for job in self.db_connector.get_jobs():
                    job_id = job['job_id']
                    if job_id.startswith("run"):
                        await self.dispatch_run(job)
                    elif job_id.startswith("composition") or job_id.startswith('run-mem3dg-'):
                        await self.dispatch_composition(job)
                i += 1
                await asyncio.sleep(wait)
        else:
            raise ValueError("You cannot call this method if a database connector is not provided in this class' constructor.")

    def create_dynamic_environment(self, job: Mapping[str, Any]) -> int:
        # TODO: implement this
        return 0

    async def dispatch_composition(self, job: Mapping[str, Any]) -> ServerResponse:
        job_status = job["status"]
        job_id = job["job_id"]
        if job_status.lower() == "pending":
            try:
                # install simulators required TODO: implement this
                self.create_dynamic_environment(job)

                # change job status to IN_PROGRESS
                if self.db_io:
                    await self.db_connector.update_job(job_id=job_id, status="IN_PROGRESS")

                # get request params and parse remote file uploads if needed
                input_state = job["spec"]
                duration = job.get("duration", 1)
                for process_name, process_spec in input_state.items():
                    process_config = process_spec["config"]
                    for config_key, config_value in process_config.items():
                        if config_key == "model":
                            source_fp = config_value["model_source"]
                            temp_dest = tempfile.mkdtemp()
                            local_fp = download_file_from_bucket(source_blob_path=source_fp, out_dir=temp_dest, bucket_name=DEFAULT_BUCKET_NAME)
                            process_spec["config"]["model"]["model_source"] = local_fp
                        elif "mesh_file" in config_key:
                            source_fp = process_config["mesh_file"]
                            temp_dest = tempfile.mkdtemp()
                            local_fp = download_file_from_bucket(source_blob_path=source_fp, out_dir=temp_dest, bucket_name=DEFAULT_BUCKET_NAME)
                            process_spec["config"]["mesh_file"] = local_fp

                # generate composition instance
                composition = self.generate_composite(input_state)

                # get composition results and state
                results = self.generate_composition_results(input_state, duration)
                state = self.generate_composition_state(composition)

                if self.db_io:
                    # change status to complete and write results in DB
                    await self.db_connector.update_job(
                        job_id=job_id,
                        status="COMPLETE",
                        results=results
                    )

                    # write new result state to states collection
                    await self.db_connector.write(
                        collection_name="result_states",
                        job_id=job_id,
                        data=state,
                        last_updated=self.db_connector.timestamp()
                    )

                return ServerResponse(
                    results=results,
                    state=state,
                )
            except Exception as e:
                message = handle_exception(scope=job_id + str(e).strip())
                logger.error(message)
                failed_job = self.generate_failed_job(job_id, message)
                await self.db_connector.update_job(**failed_job)

    def generate_composite(self, input_state) -> Composite:
        return Composite(
            config={"state": input_state},
            core=app_registrar.core
        )

    def generate_composition_results(self, composition: Composite, duration: int) -> ResultData:
        try:
            # run the composition
            composition.run(duration)

            # get the results formatted from emitter
            results = composition.gather_results()[("emitter",)]
            return ResultData(**results)
        except:
            msg = handle_exception("composition")
            return ResultData(error=msg)

    def generate_composition_state(self, composition: Composite) -> CompositionState:
        temp_dir = tempfile.mkdtemp()
        temp_fname = f"temp.state.json"
        composition.save(filename=temp_fname, outdir=temp_dir)
        temp_path = os.path.join(temp_dir, temp_fname)
        with open(temp_path, 'r') as f:
            current_data = json.load(f)
        os.remove(temp_path)

        return CompositionState(**current_data)

    async def dispatch_run(self, job: Mapping[str, Any]):
        job_status = job["status"]
        job_id = job["job_id"]
        if job_status.lower() == "pending":
            try:
                self.create_dynamic_environment(job)
                await RunsWorker().dispatch(job=job, db_connector=self.db_connector)
                return
            except Exception as e:
                message = handle_exception(scope=job_id + str(e).strip())
                logger.error(message)
                failed_job = self.generate_failed_job(job_id, message)
                await self.db_connector.update_job(**failed_job)

    @staticmethod
    def generate_failed_job(job_id: str, msg: str):
        return {"job_id": job_id, "status": "FAILED", "results": msg}




