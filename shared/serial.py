import os
import pickle
import uuid
import hashlib
import zlib
from tempfile import mkdtemp

from vivarium import Vivarium
import hmac


from shared.environment import DEFAULT_BUCKET_NAME
from shared.io import download_file, upload_blob


def get_pickle(vivarium_id: str, temp_dir: str) -> bytes:
    remote_pickle_path = get_remote_pickle_path(vivarium_id)
    local_pickle_file = download_file(remote_pickle_path, temp_dir, DEFAULT_BUCKET_NAME)
    with open(local_pickle_file, "rb") as f:
        return f.read()


def hydrate_pickle(vivarium_id: str, temp_dir: str) -> Vivarium:
    remote_pickle_path = get_remote_pickle_path(vivarium_id)
    local_pickle_file = download_file(remote_pickle_path, temp_dir, DEFAULT_BUCKET_NAME)
    with open(local_pickle_file, "rb") as f:
        return pickle.load(f)


def write_pickle(vivarium: Vivarium, vivarium_id: str) -> str:
    upload_prefix = f"file_uploads/vivarium/{vivarium_id}"
    bucket_prefix = f"gs://{DEFAULT_BUCKET_NAME}/" + upload_prefix
    local_pickle_file = f'.pckl'
    save_dest = mkdtemp()
    local_path = os.path.join(save_dest, local_pickle_file)

    # write pickle locally
    with open(local_path, "wb") as f:
        pickle.dump(vivarium, f)

    # upload local pickle to bucket
    remote_pickle_path = upload_prefix + local_path.split("/")[-1]
    upload_blob(bucket_name=DEFAULT_BUCKET_NAME, source_file_name=local_path, destination_blob_name=remote_pickle_path)

    # return remote path
    return remote_pickle_path


def get_remote_pickle_path(vivarium_id: str) -> str:
    return f"file_uploads/vivarium/{vivarium_id}.pckl"


def create_vivarium_id(vivarium: Vivarium) -> str:
    return 'vivarium-' + str(uuid.uuid4()) + '-' + str(vivarium.__hash__())


def sign_pickle(data: bytes, secret_key: bytes) -> bytes:
    """Signs the data with HMAC to prevent tampering."""
    signature = hmac.new(secret_key, data, hashlib.sha256).digest()
    return signature + data
