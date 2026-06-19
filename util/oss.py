# -*- coding: utf-8 -*-
import oss2
from oss2.credentials import EnvironmentVariableCredentialsProvider
from itertools import islice
import os
import logging
import time
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

endpoint = "https://oss-cn-beijing.aliyuncs.com"
region = "cn-beijing"
bucket_name = "your bucket name"

_bucket = None


def _oss_env_ready() -> bool:
    return bool(os.environ.get("OSS_ACCESS_KEY_ID") and os.environ.get("OSS_ACCESS_KEY_SECRET"))


def _get_bucket():
    global _bucket
    if _bucket is not None:
        return _bucket
    if not _oss_env_ready():
        raise RuntimeError(
            "OSS is not configured. Set OSS_ACCESS_KEY_ID and OSS_ACCESS_KEY_SECRET "
            "(required for voice/image upload; text-only local testing does not need them)."
        )
    auth = oss2.ProviderAuthV4(EnvironmentVariableCredentialsProvider())
    _bucket = oss2.Bucket(auth, endpoint, bucket_name, region=region)
    return _bucket


class _LazyBucket:
    """Defer OSS client creation until voice/image upload actually needs it."""

    def __getattr__(self, name):
        return getattr(_get_bucket(), name)


bucket = _LazyBucket()


def create_bucket(target_bucket=None):
    target_bucket = target_bucket or _get_bucket()
    try:
        target_bucket.create_bucket(oss2.models.BUCKET_ACL_PRIVATE)
        logging.info("Bucket created successfully")
    except oss2.exceptions.OssError as e:
        logging.error(f"Failed to create bucket: {e}")


def upload_file(target_bucket, object_name, data):
    try:
        result = target_bucket.put_object(object_name, data)
        logging.info(f"File uploaded successfully, status code: {result.status}")
    except oss2.exceptions.OssError as e:
        logging.error(f"Failed to upload file: {e}")


def download_file(target_bucket, object_name):
    try:
        file_obj = target_bucket.get_object(object_name)
        content = file_obj.read().decode('utf-8')
        logging.info("File content:")
        logging.info(content)
        return content
    except oss2.exceptions.OssError as e:
        logging.error(f"Failed to download file: {e}")


def list_objects(target_bucket):
    try:
        objects = list(islice(oss2.ObjectIterator(target_bucket), 10))
        for obj in objects:
            logging.info(obj.key)
    except oss2.exceptions.OssError as e:
        logging.error(f"Failed to list objects: {e}")


def delete_objects(target_bucket):
    try:
        objects = list(islice(oss2.ObjectIterator(target_bucket), 100))
        if objects:
            for obj in objects:
                target_bucket.delete_object(obj.key)
                logging.info(f"Deleted object: {obj.key}")
        else:
            logging.info("No objects to delete")
    except oss2.exceptions.OssError as e:
        logging.error(f"Failed to delete objects: {e}")


def delete_bucket(target_bucket):
    try:
        target_bucket.delete_bucket()
        logging.info("Bucket deleted successfully")
    except oss2.exceptions.OssError as e:
        logging.error(f"Failed to delete bucket: {e}")


if __name__ == '__main__':
    url = bucket.sign_url("GET", "test.silk", 5 * 60)
    print(url)
