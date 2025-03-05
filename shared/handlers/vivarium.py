from dataclasses import dataclass

import process_bigraph as pbg
from vivarium import Vivarium


class DynamicData:
    def __init__(self, **params):
        """Dynamically define and set state attributes via **data."""
        self._set_attributes(**params)

    def _set_attributes(self, **params):
        for k, v in params.items():
            setattr(self, k, v)

    def serialize(self) -> dict:
        return self.__dict__

    def __repr__(self) -> str:
        return str(self.serialize())


class StatefulDict(dict):
    def __new__(cls, global_time: float, *args, **kwargs):
        kwargs["global_time"] = global_time
        for k, v in kwargs.items():
            setattr(cls, k, v)
        return super(StatefulDict, cls).__new__(cls, *args, **kwargs)


class Result(StatefulDict):
    pass


@dataclass
class Results:
    data: list[Result]


# TODO: possibly have an endpoint /create-vivarium in which a vivarium instance is pickled and saved to db
# this exposes all methods of a stateful vivarium
# /add-process (vivarium_id, name, process_id): unpickle vivarium instance and run vivarium.add_process()
# /add-object (vivarium_id, name, value, path?): "" but for objects


def create_vivarium(
        document: dict = None,
        core: pbg.ProcessTypes = None
) -> Vivarium:
    import json
    from vivarium import Vivarium
    from bsp import app_registrar

    if not core:
        core = app_registrar.core

    return Vivarium(processes=core.process_registry.registry, document=document)


def parse_spec(composite_spec: dict, duration: int, core: pbg.ProcessTypes = None) -> Vivarium:
    import json
    from vivarium import Vivarium
    from bsp import app_registrar

    if not core:
        core = app_registrar.core

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

