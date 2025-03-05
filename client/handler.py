import os

from tempfile import mkdtemp

import grpc
from fastapi import UploadFile, HTTPException

from common.proto import simulation_pb2_grpc, simulation_pb2
from shared.environment import LOCAL_GRPC_MAPPING


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
    def submit_run(cls, last_updated: str, duration: int, signed_pickle: bytes, job_id: str, vivarium_id: str) -> list[dict[str, str | dict]]:
        with grpc.insecure_channel(LOCAL_GRPC_MAPPING) as channel:
            stub = simulation_pb2_grpc.VivariumServiceStub(channel)
            request = simulation_pb2.VivariumRequest(
                last_updated=last_updated,
                duration=duration,
                payload=signed_pickle,
                job_id=job_id,
                vivarium_id=vivarium_id
            )

            response_iterator = stub.StreamVivarium(request)

            # TODO: the following block should be generalized (used by many)
            results = []
            for update in response_iterator:
                # TODO: fit this into the data model!
                result = {
                    "job_id": update.job_id,
                    "last_updated": update.last_updated,
                    "results": update.results
                }
                results.append(result)
                print(f'Got result: {result}')

            return results

