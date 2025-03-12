import os

import grpc_tools.protoc


def parse_proto() -> None:
    root = os.path.dirname(os.path.dirname(__file__))
    proto_dir = os.path.join(root, "common", "proto")
    proto_file = os.path.join(proto_dir, "simulation.proto")

    proto_include = os.popen("python -c 'import grpc_tools.protoc; import os; print(os.path.dirname(grpc_tools.protoc.__file__))'").read().strip()

    return grpc_tools.protoc.main([
        "grpc_tools.protoc",
        f"-I{proto_dir}",
        f"-I{proto_include}/_proto",
        f"--python_out={proto_dir}",
        f"--grpc_python_out={proto_dir}",
        proto_file,
    ])


if __name__ == "__main__":
    parse_proto()
