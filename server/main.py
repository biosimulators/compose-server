import time
from concurrent import futures

import grpc

from common.proto import simulation_pb2, simulation_pb2_grpc
from shared.utils import timestamp
from shared.vivarium import create_vivarium, run_composition


def process_composition(job_id, simulators: list[str], duration: int, spec: dict):
    vivarium = create_vivarium(document=spec)
    for interval in range(duration):
        results = run_composition(vivarium=vivarium, duration=interval)
        yield simulation_pb2.SimulationUpdate(
            job_id=job_id,
            last_updated=timestamp(),
            results=results
        )
        # time.sleep(1)  # Simulate computation delay


class SimulationService(simulation_pb2_grpc.SimulationServiceServicer):
    def StreamSimulation(self, request, context):
        """Handles a gRPC streaming request from a client."""
        print(f"Received SimulationRequest for job_id: {request.job_id}")

        # Convert spec from gRPC message to Python dictionary
        # job_id = job_id,
        # last_updated = last_updated,
        # simulators = simulators,
        # duration = duration,
        # spec = spec

        # Run simulation and stream responses
        for update in process_composition(
                job_id=request.job_id,
                simulators=request.simulators,
                duration=request.duration,
                spec=request.spec
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
