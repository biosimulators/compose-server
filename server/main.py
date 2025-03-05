import hashlib
import hmac
import pickle
import time
from concurrent import futures

import grpc
from google.protobuf.internal.well_known_types import Struct
from vivarium import Vivarium

from common.proto import simulation_pb2, simulation_pb2_grpc
from shared.environment import TEST_KEY
from shared.serial import get_remote_pickle_path, write_pickle
from shared.utils import timestamp
from shared.vivarium import create_vivarium, run_composition, convert_process


class ServerHandler:
    @classmethod
    def verify_pickle(cls, signed_data: bytes, secret_key: bytes) -> bytes:
        """Verify HMAC and return raw compressed pickle data."""
        signature = signed_data[:32]
        data: bytes = signed_data[32:]

        expected_sig = hmac.new(secret_key, data, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected_sig):
            raise ValueError("Pickle signature verification failed")
        return data

    @classmethod
    def convert_dict_to_struct(cls, data: dict) -> Struct:
        """Converts a Python dictionary to a Protobuf Struct."""
        proto_struct = Struct()
        proto_struct.update(data)
        return proto_struct

    @classmethod
    def process_run(cls, duration: int, signed_pickle: bytes, job_id: str, vivarium_id: str, buffer: float = 0.05):
        try:
            safe_pickle = cls.verify_pickle(signed_pickle, TEST_KEY)
            vivarium: Vivarium = pickle.loads(safe_pickle)
            for _ in range(duration):
                # run simulation for k
                vivarium.run(1)  # TODO: make this timestep more controllable and smaller
                results_k = vivarium.get_results()

                proto_results = [
                    simulation_pb2.Result(data=cls.convert_dict_to_struct(result))
                    for result in results_k
                ]

                # stream kth update
                yield simulation_pb2.SimulationUpdate(
                    job_id=job_id,
                    last_updated=timestamp(),
                    results=proto_results
                )

                # write the updated vivarium state to the pickle file
                # remote_pickle_path = get_remote_pickle_path(vivarium_id)
                # write_pickle(vivarium_id=vivarium_id, vivarium=vivarium)

                # add buffer: TODO: do we need this?
                time.sleep(buffer)
        except Exception as e:
            print(e)
            raise grpc.RpcError(grpc.StatusCode.INTERNAL, str(e))


class VivariumService(simulation_pb2_grpc.VivariumServiceServicer):
    def StreamVivarium(self, request, context):
        """Handles a gRPC streaming request from a client."""
        print(f"Received SimulationRequest for job_id: {request.job_id}")

        # Run simulation and stream responses
        for update in ServerHandler.process_run(
                job_id=request.job_id,
                duration=request.duration,
                signed_pickle=request.payload,
                vivarium_id=request.vivarium_id
        ):
            yield update


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    simulation_pb2_grpc.add_VivariumServiceServicer_to_server(VivariumService(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    print("gRPC Server started on port 50051...")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
