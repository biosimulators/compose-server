"""
Server gateway implementation.

Author: Alexander Patrie <@AlexPatrie>
"""

import json
import os
import shutil
import uuid
import sys
import zlib
from tempfile import mkdtemp
from typing import *
import asyncio
from functools import partial
# import websockets


import dotenv
import grpc
import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException, Query, APIRouter, Body, WebSocket, Response, Depends
from google.protobuf.json_format import MessageToDict
from process_bigraph import Process, pp, Composite
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse
from pydantic import BeforeValidator
from google.protobuf.struct_pb2 import Struct
from google.protobuf.any_pb2 import Any
from vivarium import Vivarium
from vivarium.tests import TOY_PROCESSES, DEMO_PROCESSES  # TODO: replace these

from client.handler import ClientHandler
from client.submit_runs import submit_utc_run, submit_pymem3dg_run
from common.proto import simulation_pb2_grpc, simulation_pb2
from shared.connect import MongoConnector
from yaml import compose

from shared.io import write_uploaded_file, download_file_from_bucket, write_local_file
from shared.log_config import setup_logging
from shared.serial import write_pickle, create_vivarium_id, hydrate_pickle, get_pickle, sign_pickle, get_remote_pickle_path
from shared.utils import get_project_version, new_job_id, handle_exception, serialize_numpy, clean_temp_files, timestamp
from shared.environment import (
    ENV_PATH,
    DEFAULT_DB_NAME,
    DEFAULT_JOB_COLLECTION_NAME,
    DEFAULT_BUCKET_NAME, LOCAL_GRPC_MAPPING, TEST_KEY
)
from shared.data_model import (
    BigraphRegistryAddresses,
    CompositionNode,
    CompositionSpec,
    CompositionRun,
    OutputData,
    ValidatedComposition,
    SmoldynRun,
    SimulariumAgentParameters,
    ReaddySpeciesConfig,
    ReaddyReactionConfig,
    ReaddyParticleConfig,
    ReaddyRun,
    AmiciRun,
    CobraRun,
    CopasiRun,
    TelluriumRun,
    IncompleteFileJob,
    APP_SERVERS,
    HealthCheckResponse,
    ProcessMetadata,
    Mem3dgRun,
    BigraphSchemaType,
    StateData,
    FileUpload
)

from client.health import check_client
from shared.vivarium import CORE, check_composition, convert_process

logger = setup_logging(__file__)

# NOTE: create an env config at this filepath if dev
dotenv.load_dotenv(ENV_PATH)

STANDALONE_GATEWAY = bool(os.getenv("STANDALONE_GATEWAY"))
MONGO_URI = os.getenv("MONGO_URI") if not STANDALONE_GATEWAY else os.getenv("STANDALONE_MONGO_URI")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# -- app constraints and components -- #

APP_VERSION = get_project_version()
APP_TITLE = "compose-server"
APP_ORIGINS = [
    'http://127.0.0.1:8000',
    'http://127.0.0.1:4200',
    'http://127.0.0.1:4201',
    'http://127.0.0.1:4202',
    'http://localhost:4200',
    'http://localhost:4201',
    'http://localhost:4202',
    'http://localhost:8000',
    'http://localhost:3001',
    'https://biosimulators.org',
    'https://www.biosimulators.org',
    'https://biosimulators.dev',
    'https://www.biosimulators.dev',
    'https://run.biosimulations.dev',
    'https://run.biosimulations.org',
    'https://biosimulations.dev',
    'https://biosimulations.org',
    'https://bio.libretexts.org',
    'https://compose.biosimulations.org'
]

db_conn_gateway = MongoConnector(connection_uri=MONGO_URI, database_id=DEFAULT_DB_NAME)
router = APIRouter()
app = FastAPI(title=APP_TITLE, version=APP_VERSION, servers=APP_SERVERS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
app.mongo_client = db_conn_gateway.client

PyObjectId = Annotated[str, BeforeValidator(str)]


def optional_file(document: UploadFile = File(default=None)):
    return document


class ClientHandler:
    @classmethod
    async def parse_uploaded_files_in_spec(cls, model_files: list[UploadFile], config_data: dict) -> list[str]:
        temp_files = []
        # parse config for model specification TODO: generalize this
        for uploaded_file in model_files:
            # case: has a SedModel config spec (ode, fba, smoldyn)
            if "model" in config_data.keys():
                specified_model = config_data["model"]["model_source"]
                if uploaded_file.filename == specified_model.split("/")[-1]:
                    temp_dir = mkdtemp()
                    temp_file = os.path.join(temp_dir, uploaded_file.filename)
                    with open(temp_file, "wb") as f:
                        uploaded = await uploaded_file.read()
                        f.write(uploaded)
                    config_data["model"]["model_source"] = temp_file
                    temp_files.append(temp_file)
            # case: has a mesh file config (membrane)
            elif "mesh_file" in config_data.keys():
                temp_dir = mkdtemp()
                temp_file = os.path.join(temp_dir, uploaded_file.filename)
                with open(temp_file, "wb") as f:
                    uploaded = await uploaded_file.read()
                    f.write(uploaded)
                config_data["mesh_file"] = temp_file
                temp_files.append(temp_file)
        return temp_files

    @classmethod
    def check_document_extension(cls, document: UploadFile) -> None:
        if not document.filename.endswith('.json') and document.content_type != 'application/json':
            raise HTTPException(status_code=400, detail="Invalid file type. Only JSON files are supported.")

    @classmethod
    def submit_run(cls, last_updated: str, duration: int, pickle_path: str, job_id: str, vivarium_id: str) -> list[list[dict[str, str | dict]]]:
        with grpc.insecure_channel(LOCAL_GRPC_MAPPING) as channel:
            stub = simulation_pb2_grpc.VivariumServiceStub(channel)
            request = simulation_pb2.VivariumRequest(
                last_updated=last_updated,
                duration=duration,
                pickle_path=pickle_path,
                job_id=job_id,
                vivarium_id=vivarium_id
            )

            response_iterator = stub.StreamVivarium(request)

            # TODO: the following block should be generalized (used by many)
            results = []
            for update in response_iterator:
                structured_results = [
                    MessageToDict(result)
                    for result in update.results
                ]
                results.append(structured_results)

            return results


@app.post(
    "/new-vivarium",
    name="Create new vivarium",
    operation_id="new-vivarium",
    tags=["Composition"],
)
async def create_new_vivarium(document: UploadFile = Depends(optional_file)):
    # compile all possible registrations TODO: generalize/streamline this
    registered_processes: dict = CORE.process_registry.registry
    registered_processes.update(TOY_PROCESSES)
    registered_processes.update(DEMO_PROCESSES)

    # assume no document at first
    composite_spec: dict[str, str | dict] | None = None

    # handle document upload
    if document is not None:
        ClientHandler.check_document_extension(document)

        file_content: bytes = await document.read()
        composite_spec: dict[str, str | dict] = json.loads(file_content)

    # create new viv instance and add emitter
    viv = Vivarium(document=composite_spec, processes=registered_processes, types=CORE.types())
    viv.add_emitter()

    # write pickled viv to bucket and get remote location
    new_id: str = create_vivarium_id(viv)
    remote_vivarium_pickle_path = write_pickle(viv, new_id)

    return {'vivarium_id': new_id, 'remote_path': remote_vivarium_pickle_path}


@app.post(
    '/run-vivarium',
    name="Run vivarium",
    operation_id="run-vivarium",
    tags=["Composition"],
)
async def run_vivarium(duration: int, vivarium_id: str = Query(default=None)):  # , document: UploadFile = Depends(optional_file)):
    # create new vivarium if no id passed
    if vivarium_id is None:
        new_viv_response: dict[str, str] = await create_new_vivarium()  # (document)
        vivarium_id: str = new_viv_response['vivarium_id']

    # get the pickle as bytes data from the vivarium_id
    pickle_path = get_remote_pickle_path(vivarium_id)
    last_updated: str = timestamp()
    job_id: str = new_job_id('run-vivarium')

    return ClientHandler.submit_run(
        last_updated=last_updated,
        duration=duration,
        pickle_path=pickle_path,
        job_id=job_id,
        vivarium_id=vivarium_id
    )


@app.get(
    '/get-document',
    name="Get document",
    operation_id="get-document",
    summary="Get the document required to instantiate a new Vivarium instance corresponding to the given vivarium_id",
    tags=["Composition"],
)
async def get_document(vivarium_id: str):
    # hydrate pickle into vivarium
    temp_dir = mkdtemp()
    vivarium: Vivarium = hydrate_pickle(vivarium_id, temp_dir)

    # clean temp dir
    shutil.rmtree(temp_dir)

    return vivarium.make_document()


@app.get(
    '/_get-pickle',
    operation_id="_get-pickle",
    tags=["Composition"],
    name="_get-pickle",
    response_class=Response
)
async def _get_pickle(vivarium_id: str) -> Response:
    temp_dir = mkdtemp()
    p: bytes = get_pickle(vivarium_id, temp_dir)
    compressed_pickle = zlib.compress(p)
    signed_pickle = sign_pickle(compressed_pickle, TEST_KEY)
    return Response(content=signed_pickle, media_type="application/octet-stream")


# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=3001)

