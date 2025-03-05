import hashlib
import hmac
import time
from concurrent import futures

import grpc

from common.proto import simulation_pb2, simulation_pb2_grpc
from shared.utils import timestamp
from shared.vivarium import create_vivarium, run_composition, convert_process


def verify_pickle(signed_data: bytes, secret_key: bytes) -> bytes:
    """Verify HMAC and return raw compressed pickle data."""
    signature = signed_data[:32]
    data: bytes = signed_data[32:]

    expected_sig = hmac.new(secret_key, data, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_sig):
        raise ValueError("Pickle signature verification failed")

    return data

class SimulationService(simulation_pb2_grpc.SimulationServiceServicer):
    def StreamSimulation(self, request, context):
        """Handles a gRPC streaming request from a client."""
        print(f"Received SimulationRequest for job_id: {request.job_id}")

        # convert spec from gRPC message to Python dictionary
        spec = {k: convert_process(v) for k, v in request.spec.items()}

        # Run simulation and stream responses
        for update in process_composition(
                job_id=request.job_id,
                simulators=request.simulators,
                duration=request.duration,
                spec=spec
        ):
            yield update


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    simulation_pb2_grpc.add_SimulationServiceServicer_to_server(SimulationService(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    print("gRPC Server started on port 50051...")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
