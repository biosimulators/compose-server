import os
import traceback
import uuid
from enum import Enum, EnumMeta
from asyncio import sleep
from typing import *
from pprint import pformat

import h5py
import numpy as np


def clean_temp_files(temp_files: List[os.PathLike[str] | str]):
    return [os.remove(temp_file) for temp_file in temp_files if len(temp_files)]


def serialize_numpy(obj: Union[np.ndarray, list, dict]) -> Union[np.ndarray, list, dict]:
    """Recursively convert NumPy arrays inside a dictionary or list into lists."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: serialize_numpy(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_numpy(item) for item in obj]
    else:
        return obj


def handle_exception(scope: str) -> str:
    tb_str = traceback.format_exc()
    error_message = pformat(f"{scope}:\n{tb_str}")
    return error_message


def new_job_id(tag: str) -> str:
    return f"{tag}-{unique_id()}"


def unique_id() -> str:
    return str(uuid.uuid4())


def stdout_colors():
    # ANSI colors TODO: add more
    class StdoutColors(Enum):
        SKY_BLUE = "\033[38;5;117m"
        LIGHT_PURPLE = "\033[38;5;183m"
        ERROR_RED = "\033[31m"
        CURSOR_YELLOW = "\033[33m"
        MAGENTA = "\033[35m"
        RESET = "\033[0m"
    return StdoutColors


def file_upload_prefix(job_id: str, BUCKET_NAME: str) -> tuple[str, str]:
    # bucket params
    upload_prefix = f"file_uploads/{job_id}/"
    bucket_prefix = f"gs://{BUCKET_NAME}/" + upload_prefix
    return upload_prefix, bucket_prefix


def visit_datasets(
        group: Union[h5py.File, h5py.Group],
        group_path: Optional[str] = None
) -> dict[str, np.ndarray]:
    matching_datasets = {}
    for name, obj in group.items():
        gp = group_path or ""
        full_path = f"{group_path}/{name}" if group_path else name
        if "report" in full_path:
            matching_datasets[full_path] = obj[()]
        else:
            if isinstance(obj, h5py.Group):
                matching_datasets.update(visit_datasets(obj, full_path))
    return matching_datasets


def handle_sbml_exception() -> str:
    tb_str = traceback.format_exc()
    error_message = pformat(f"time-course-simulation-error:\n{tb_str}")
    return error_message


def printc(msg: Any, alert: str = '', error=False):
    StdoutColors = stdout_colors()
    prefix = f"{StdoutColors.CURSOR_YELLOW.value if not error else StdoutColors.ERROR_RED.value}{alert if not error else 'AN ERROR OCCURRED'}:{StdoutColors.RESET.value}"
    message = f"{StdoutColors.SKY_BLUE.value if not error else StdoutColors.ERROR_RED.value}{msg}{StdoutColors.RESET.value}\n"
    content = f"{StdoutColors.MAGENTA.value}>{StdoutColors.RESET.value} "
    if alert:
        content += f"{prefix} {message}"
    else:
        content += f" {message}"
    print(content)


# -- formatted observables data -- #

def get_output_stack(spec_name: str, output):
    # 2. in output_stack: return {simname: output}
    stack = {}
    for simulator_name in output.keys():
        spec_data = output[simulator_name].get(spec_name)
        if isinstance(spec_data, str):
            data = None
        else:
            data = spec_data

        stack[simulator_name] = data

    return stack


async def load_arrows(timer):
    check_timer = timer
    ell = ""
    bars = ""
    msg = "|"
    n_ellipses = timer
    log_interval = check_timer / n_ellipses
    for n in range(n_ellipses):
        single_interval = log_interval / 3
        await sleep(single_interval)
        bars += "="
        disp = bars + ">"
        if n == n_ellipses - 1:
            disp += "|"
        print(disp)


def get_project_attribute(attribute: str):
    import toml
    current_filename = os.path.abspath(__file__)
    shared_dirpath = os.path.abspath(
        os.path.dirname(current_filename)
    )
    root_dirpath = os.path.dirname(shared_dirpath)
    pyproject_fp = os.path.join(root_dirpath, "pyproject.toml")

    return toml.load(pyproject_fp)["project"][attribute]


def get_project_version() -> str:
    return get_project_attribute("version")
