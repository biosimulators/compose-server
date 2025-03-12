# -- gateway models -- #
# -- worker models -- #
import os
from dataclasses import dataclass, asdict, field
import abc
import dataclasses as dc
from enum import Enum
from typing import *

from dotenv import load_dotenv
from pydantic import Field, BaseModel as _BaseModel, ConfigDict
from fastapi.responses import FileResponse
import numpy as np


class BaseModel(_BaseModel):
    """Base Pydantic Model with custom app configuration"""
    model_config = ConfigDict(arbitrary_types_allowed=True)


@dataclass
class BaseClass:
    """Base Python Dataclass multipurpose class with custom app configuration."""
    def serialize(self):
        return asdict(self)

    def set(self, attribute_id: str, value: float | int | str | bool | list | dict):
        return setattr(self, attribute_id, value)

    def get(self, attribute_id: str):
        return getattr(self, attribute_id)

    @property
    def attributes(self) -> list[str]:
        return list[self.__dataclass_fields__.keys()]


# --- vivarium interface ---

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
    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        return instance

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class Result(dict):
    def __new__(cls, global_time: float, *args, **kwargs):
        instance = super().__new__(cls)
        instance.global_time = global_time
        return instance

    def __init__(self, global_time: float, *args, **kwargs):
        super().__init__(*args, **kwargs)


@dataclass
class RunResponse(BaseClass):
    job_id: str
    last_updated: str
    results: list[dict[str, Any] | Result]


@dataclass
class Results:
    data: list[Result]


# -- requests --

@dataclass
class FileUpload:
    location: str
    job_id: str
    status: str


@dataclass
class ProcessMetadata(BaseClass):
    process_address: str
    input_schema: Dict
    output_schema: Dict
    initial_state: Dict
    state: Optional[Dict] = field(default=None)


@dataclass
class BigraphSchemaType(BaseClass):
    type_id: str
    default_value: str
    description: str


@dataclass
class Run(BaseClass):
    job_id: str
    last_updated: str
    status: str


@dataclass
class CompositionRun(Run):
    simulators: List[str]
    duration: int
    spec: Dict[str, Any]
    results: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SmoldynRun(Run):
    path: str
    duration: float
    dt: float



@dataclass
class Mem3dgRun(CompositionRun):
    """
    :param simulators:
    :param duration:
    :param spec:
    :param results:
    """
    pass


@dataclass
class _Mem3dgRun(Run):
    characteristic_time_step: float
    tension_modulus: float
    preferred_area: float
    preferred_volume: float
    reservoir_volume: float
    osmotic_strength: float
    volume: float
    parameters_config: dict[str, float | int]
    damping: float
    tolerance: Optional[float] = 1e-11
    geometry_type: Optional[str] = None
    geometry_parameters: Optional[Dict[str, Union[float, int]]] = None
    mesh_file: Optional[str] = None


@dataclass
class UtcRun(Run):
    simulator: str
    model_file: str
    start: int
    stop: int
    steps: int
    params: Dict[str, Any] = field(default=None)


@dataclass
class AmiciRun(UtcRun):
    pass


@dataclass
class CobraRun(UtcRun):
    pass


@dataclass
class CopasiRun(UtcRun):
    pass


@dataclass
class TelluriumRun(UtcRun):
    pass


@dataclass
class ReaddySpeciesConfig(BaseClass):
    name: str
    diffusion_constant: float


@dataclass
class ReaddyReactionConfig(BaseClass):
    scheme: str
    rate: float


@dataclass
class ReaddyParticleConfig(BaseClass):
    name: str
    initial_positions: List[List[float]]


@dataclass
class ReaddyRun(Run):
    duration: float
    dt: float
    box_size: List[float]
    species_config: Union[Dict[str, float], List[ReaddySpeciesConfig]]
    particles_config: Union[Dict[str, List[List[float]]], List[ReaddyParticleConfig]]
    reactions_config: Union[Dict[str, float], List[ReaddyReactionConfig]]
    unit_system_config: Dict[str, Any]
    reaction_handler: str


@dataclass
class SimulariumAgentParameter(BaseClass):
    name: str
    radius: Optional[float]
    mass: Optional[float]
    density: Optional[float]


@dataclass
class SimulariumAgentParameters(BaseClass):
    agents: List[SimulariumAgentParameter]


@dataclass
class DbClientResponse(BaseClass):
    message: str
    db_type: str  # ie: 'mongo', 'postgres', etc
    timestamp: str
    status: str = field(default=None)  # either PASS or FAIL


# -- process-bigraph specs --

@dataclass
class BigraphRegistryAddresses(BaseClass):
    version: str
    registered_addresses: List[str]


class DataStorePath(str):
    pass


@dataclass
class DataStore(BaseClass):
    paths: List[DataStorePath | str] | str

    def __post_init__(self):
        if isinstance(self.paths, str):
            self.paths = [DataStorePath(self.paths)]
        else:
            paths = {
                path_i: path for path_i, path in enumerate(self.paths)
            }
            for i, path in paths.items():
                if isinstance(path, str):
                    paths[i] = DataStorePath(path)
            self.paths = list(paths.values())


@dataclass
class PortStore(BaseClass):
    name: str  # outermost keys under "inputs"
    store: DataStore | List[str]  # ie: ["concentrations_store"]

    def __post_init__(self):
        if isinstance(self.store, list):
            self.store = DataStore(self.store)


@dataclass
class Port(BaseClass):
    name: str
    value: Any


@dataclass
class InputPort(Port):
    pass


@dataclass
class OutputPort(Port):
    pass


@dataclass
class CompositionNode(BaseClass):
    name: str
    _type: str
    address: str
    config: DynamicData
    inputs: Optional[list[InputPort]] = field(default_factory=list)
    outputs: Optional[list[OutputPort]] = field(default_factory=list)

    def _format_port(self, ports: list[InputPort | OutputPort]) -> dict[str, Any]:
        return {port.name: port.value for port in ports}

    def export(self) -> dict[str, Any]:
        rep = self.serialize()
        del rep['name']
        rep['inputs'] = self._format_port(self.inputs)
        rep['outputs'] = self._format_port(self.outputs)
        return rep


@dataclass
class CompositionSpec(BaseClass):
    """To be used as input to process_bigraph.Composition() like:

        spec = CompositionSpec(nodes=nodes, emitter_mode='ports')
        composite = Composition({'state': spec
    """
    nodes: list[CompositionNode]

    def export(self):
        return {
            node_spec.name: node_spec.export()
            for node_spec in self.nodes
        }


# -- output data/responses --

@dataclass
class OutputData(BaseClass):
    job_id: str
    status: str
    last_updated: str
    results: Dict


class SmoldynOutput(FileResponse):
    pass


@dataclass
class ValidatedComposition(BaseClass):
    valid: bool
    invalid_nodes: Optional[list[dict[str, str]]] = field(default=None)
    composition: Optional[CompositionSpec] = field(default=None)


@dataclass
class OutputFile(BaseClass):
    results_file: str


# -- misc --

@dataclass
class HealthCheckResponse(BaseClass):
    version: str
    status: str
    message: str = field(default="Welcome to the BioCompose API")
    swagger_ui: str = field(default="https://compose.biosimulations.org/docs")


@dataclass
class IncompleteFileJob(BaseClass):
    job_id: str
    timestamp: float
    status: str
    source: str


@dataclass
class MembraneConfig(BaseClass):
    characteristic_time_step: float



class JobStatuses:
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


APP_SERVERS = [
    # {
    #     "url": "https://compose.biosimulations.org",
    #     "description": "Production server"
    # },
    # {
    #     "url": "http://localhost:3001",
    #     "description": "Main Development server"
    # },
    # {
    #     "url": "http://localhost:8000",
    #     "description": "Alternate Development server"
    # }
]


# --- websocket client ---

# This class represents a change to object values (x, y, z are placeholders)
@dataclass
class Packet(BaseClass):
    dx: float
    dy: float
    dz: float


# --- websocket server ---

class StateData(DynamicData):
    pass


class AccumulationState(StateData):
    def set_data(self, **params):
        for k, v in params.items():
            prev = getattr(self, k)
            setattr(self, k, prev + v)


@dataclass
class Region(BaseClass):
    region_id: str
    metadata: dict[str, str]


@dataclass
class BodyRegionState(AccumulationState):
    region: Region
    state: AccumulationState


@dataclass
class Patient(BaseClass):
    name: str
    dob: str
    age: float
    history_metadata: dict[str, str]


@dataclass
class BodyState(AccumulationState):
    patient: Patient
    region_states: list[BodyRegionState]






