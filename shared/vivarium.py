import json
from dataclasses import dataclass

import process_bigraph as pbg
from vivarium import Vivarium
from bsp import app_registrar

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
    vivarium = Vivarium(processes=core.process_registry.registry, document=document)
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


def check_composition(document_data: dict) -> ValidatedComposition:
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
    return ValidatedComposition(**validation)

