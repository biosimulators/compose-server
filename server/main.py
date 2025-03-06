import hashlib
import hmac
import logging
import pickle
import time
from concurrent import futures
from tempfile import mkdtemp

import grpc
from google.protobuf.struct_pb2 import Struct
from vivarium import Vivarium

from common.proto import simulation_pb2, simulation_pb2_grpc
from shared.environment import TEST_KEY
from shared.serial import get_remote_pickle_path, write_pickle, hydrate_pickle
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
    def process_run(cls, duration: int, pickle_path: str, job_id: str, vivarium_id: str, buffer: float = 0.05):
        try:
            tmp = mkdtemp()
            vivarium: Vivarium = hydrate_pickle(vivarium_id=vivarium_id, temp_dir=tmp)

            for _ in range(duration):
                # run simulation for k
                vivarium.run(1)  # TODO: make this timestep more controllable and smaller
                results_k = vivarium.get_results()
                if not isinstance(results_k, list):
                    print(f'Results is not a list!')
                    print(type(results_k))

                # convert data
                proto_results = []
                for result in results_k:
                    struct = Struct()
                    struct.update(result)
                    proto_results.append(struct)

                # stream kth update
                update = simulation_pb2.SimulationUpdate(
                    job_id=job_id,
                    last_updated=timestamp(),
                    results=proto_results
                )
                print(f'Server is streaming update: {update}')
                yield update

                # write the updated vivarium state to the pickle file
                # remote_pickle_path = get_remote_pickle_path(vivarium_id)
                # write_pickle(vivarium_id=vivarium_id, vivarium=vivarium)

                # add buffer: TODO: do we need this?
                print(f'Sleeping')
                time.sleep(5)
        except Exception as e:
            print(e)
            raise grpc.RpcError(grpc.StatusCode.INTERNAL, str(e))


class VivariumService(simulation_pb2_grpc.VivariumServiceServicer):
    # def SendData(self, request, context):
    #     """Handles a single request-response gRPC call."""
    #     self.update_state(request)
    #     logging.info(f"Updated state: {self.state}")
    #     return service_pb2.BodyStateData(x=self.state.x, y=self.state.y, z=self.state.z)

    def StreamVivarium(self, request, context):
        """Handles a gRPC streaming request from a client."""
        for update in ServerHandler.process_run(duration=request.duration, pickle_path=request.pickle_path, job_id=request.job_id, vivarium_id=request.vivarium_id):
            print(f'Server processed the update: {update}')
            yield update
        # Run simulation and stream responses
        # for update in ServerHandler.process_run(
        #         job_id=request.job_id,
        #         duration=request.duration,
        #         signed_pickle=request.payload,
        #         vivarium_id=request.vivarium_id
        # ):
        #     yield update


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    simulation_pb2_grpc.add_VivariumServiceServicer_to_server(VivariumService(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    print("gRPC Server started on port 50051...")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
