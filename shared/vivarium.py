import json
from dataclasses import dataclass
from typing import Any

import process_bigraph as pbg
from google.protobuf.internal.well_known_types import Struct, Any as _Any
from vivarium import Vivarium
from vivarium.tests import TOY_PROCESSES
from bsp import app_registrar

from common.proto import simulation_pb2
from shared.data_model import Results, Result, ValidatedComposition
from shared.utils import deserialize_composition

CORE: pbg.ProcessTypes = app_registrar.core


# TODO: possibly have an endpoint /create-vivarium in which a vivarium instance is pickled and saved to db
# this exposes all methods of a stateful vivarium
# /add-process (vivarium_id, name, process_id): unpickle vivarium instance and run vivarium.add_process()
# /add-object (vivarium_id, name, value, path?): "" but for objects


def create_vivarium(
        document: dict = None,
        core: pbg.ProcessTypes = CORE
) -> Vivarium:
    processes_to_use = [core.process_registry.registry, TOY_PROCESSES]
    vivarium = Vivarium(processes=processes_to_use, document=document)
    vivarium.add_emitter()
    return vivarium


def parse_spec(composite_spec: dict, duration: int, core: pbg.ProcessTypes = CORE) -> Vivarium:
    vivarium = Vivarium(core=core)  # load in bsp.app_registrar.core
    for process_name, spec in composite_spec.items():
        vivarium.add_process(
            name=process_name,
            process_id=spec.get('address'),
            config=spec.get('config'),
            inputs=spec.get('inputs'),
            outputs=spec.get('outputs')
        )
    vivarium.add_emitter()

    return vivarium


def run_composition(vivarium: Vivarium, duration: int) -> Results:
    vivarium.run(duration)
    return Results(
        data=[
            Result(**result)
            for result in vivarium.get_results()
        ]
    )


def check_composition(document_data: dict) -> ValidatedComposition | Any:
    validation = {'valid': True}

    # validation 1 (fit data model)
    try:
        validation['composition'] = deserialize_composition(document_data)
    except:
        validation['valid'] = False
        validation['composition'] = None

    # validation 2
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
    # return ValidatedComposition(**validation)
    return validation


# TODO: handle these differently

def convert_object(key, data):
    """Converts a Python dictionary into a gRPC Object message."""
    any_value = _Any()
    any_value.Pack(convert_struct(key, data))
    return simulation_pb2.Object(value=any_value)


def convert_struct(key, data):
    """Converts a Python dictionary into a gRPC Struct message."""
    d = eval(data) if isinstance(data, str) else data
    struct = Struct()
    struct.update({key: d})
    return struct


def convert_process(process_dict):
    """Converts a Python dictionary to a gRPC Process message."""
    address = process_dict["address"]
    _type = 'step' if 'emitter' in address else 'process'
    outputs = process_dict.get('outputs')
    return simulation_pb2.Process(
        type=process_dict.get('_type', _type),
        address=address,
        config={k: convert_struct(k, v) for k, v in process_dict.get("config", {}).items()},
        inputs={k: convert_object(k, v) for k, v in process_dict.get("inputs", {}).items()},
        outputs={k: convert_object(k, v) for k, v in outputs.items()} if outputs else {},
    )

