import importlib
import uuid
from logging import Logger
from typing import *

from fastapi import UploadFile, HTTPException
from process_bigraph import Composite

from shared.data_model import UtcRun, AmiciRun, CobraRun, CopasiRun, TelluriumRun, ValidatedComposition, Mem3dgRun
from shared.database import DatabaseConnector
from shared.environment import DEFAULT_JOB_COLLECTION_NAME, DEFAULT_BUCKET_NAME
from shared.io import write_uploaded_file

from gateway.handlers.states import generate_mem3dg_state


async def submit_pymem3dg_run(
        db_connector: DatabaseConnector,
        job_id: str,
        characteristic_time_step: float,
        tension_modulus: float,
        preferred_area: float,
        preferred_volume: float,
        reservoir_volume: float,
        osmotic_strength: float,
        volume: float,
        parameters_config: dict[str, float | int],
        damping: float,
        duration: int,
        tolerance: Optional[float] = 1e-11,
        geometry_type: Optional[str] = None,
        geometry_parameters: Optional[Dict[str, Union[float, int]]] = None,
        mesh_file: Optional[str] = None,
):
    input_state = generate_mem3dg_state(
        characteristic_time_step=characteristic_time_step,
        tension_modulus=tension_modulus,
        preferred_area=preferred_area,
        preferred_volume=preferred_volume,
        reservoir_volume=reservoir_volume,
        osmotic_strength=osmotic_strength,
        volume=volume,
        parameters_config=parameters_config,
        damping=damping,
        tolerance=tolerance,
        geometry_type=geometry_type,
        geometry_parameters=geometry_parameters,
        mesh_file=mesh_file
    )

    mem3dg_job = Mem3dgRun(
        job_id=job_id,
        last_updated=db_connector.timestamp(),
        status="PENDING",
        simulators=["pymem3dg"],
        duration=duration,
        spec=input_state
    )

    # save job to db
    await db_connector.write(
        collection_name=DEFAULT_JOB_COLLECTION_NAME,
        **mem3dg_job.serialize()
    )

    return mem3dg_job


async def submit_utc_run(
        db_connector: DatabaseConnector,
        simulator: str,
        model_file: UploadFile,
        implementation_scope: str,  # either 'process' or 'step' or 'p' or 's'
        start: int,
        stop: int,
        steps: int,
        logger: Logger,
        **params
) -> AmiciRun | CobraRun | CopasiRun | TelluriumRun:
    """
    :param db_connector: database connector singleton
    :param simulator: simulator used
    :param model_file: model file (sbml)
    :param implementation_scope: one of either: 'process', 'step', 'p', 's'
    :param start: simulation start time
    :param stop: simulation stop time
    :param steps: simulation steps
    :param logger: logger from current __file__
    """
    try:
        # parse process or step and simulator for correct path routing
        if len(implementation_scope) == 1:
            implementation_scope += "rocess" if "p" in implementation_scope else "tep"
        job_id = f"run-{simulator}-{implementation_scope}-" + str(uuid.uuid4())

        # upload model file to bucket
        remote_model_path = await write_uploaded_file(
            job_id=job_id,
            uploaded_file=model_file,
            bucket_name=DEFAULT_BUCKET_NAME,
            extension='.xml'
        )

        # fit/validate data to return structure
        data_models = importlib.import_module("shared.data_model")
        ContextModel = getattr(
            data_models,
            simulator.replace(simulator[0], simulator[0].upper())
        )

        run_data: AmiciRun | CobraRun | CopasiRun | TelluriumRun = ContextModel(
            job_id=job_id,
            last_updated=db_connector.timestamp(),
            status="PENDING",
            simulator=simulator,
            model_file=remote_model_path,
            start=start,
            stop=stop,
            steps=steps,
            params=params
        )

        # save job to db
        await db_connector.write(
            collection_name=DEFAULT_JOB_COLLECTION_NAME,
            **run_data.serialize()
        )

        return run_data
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


# -- spec validation --

def check_composition(document_data: Dict) -> ValidatedComposition:
    validation = {'valid': True}
    invalid_nodes = []
    for node_name, node_spec in document_data.items():
        if "emitter" not in node_name:
            try:
                assert node_spec["inputs"], f"{node_name} is missing inputs"
                assert node_spec["outputs"], f"{node_name} is missing outputs"
            except AssertionError as e:
                invalid_node = {node_name: str(e)}
                invalid_nodes.append(invalid_node)
                validation['valid'] = False

    validation['invalid_nodes'] = invalid_nodes if len(invalid_nodes) else None
    return ValidatedComposition(**validation)
