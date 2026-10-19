"""
Author: Zulqarnain Ahmad (Freelancer: https://www.freelancer.com/u/zulqarnaina43)
In collaboration with team leader: Afaq Ahmad (Freelancer: https://www.freelancer.com/u/AFAQCEO , GitHub: https://github.com/H-tech-AFAQ-CEO)

Storage abstraction: local filesystem or Azure Blob (managed identity, no keys in code).
"""
from __future__ import annotations
import json, os, time
from pathlib import Path


class LockHeld(Exception):
    pass


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _p(self, key):
        p = self.root / key
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def write_text(self, key: str, text: str):
        p = self._p(key)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, p)  # atomic

    def read_text(self, key: str) -> str | None:
        p = self.root / key
        return p.read_text(encoding="utf-8") if p.exists() else None

    def acquire_lock(self, name: str, ttl: int = 12 * 3600):
        p = self._p(f"locks/{name}.lock")
        if p.exists() and time.time() - p.stat().st_mtime < ttl:
            raise LockHeld(f"lock {name} held")
        p.write_text(str(os.getpid()))
        return p

    def release_lock(self, handle):
        Path(handle).unlink(missing_ok=True)


class AzureBlobStorage:
    def __init__(self, account_url: str, container: str):
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient
        self.svc = BlobServiceClient(account_url, credential=DefaultAzureCredential())
        self.cc = self.svc.get_container_client(container)
        if not self.cc.exists():
            self.cc.create_container()

    def write_text(self, key, text):
        self.cc.upload_blob(key, text.encode("utf-8"), overwrite=True)

    def read_text(self, key):
        from azure.core.exceptions import ResourceNotFoundError
        try:
            return self.cc.download_blob(key).readall().decode("utf-8")
        except ResourceNotFoundError:
            return None

    def acquire_lock(self, name, ttl=0):
        """Blob lease = distributed mutex; prevents overlapping runs for the same job."""
        from azure.core.exceptions import HttpResponseError
        bc = self.cc.get_blob_client(f"locks/{name}.lock")
        if not bc.exists():
            bc.upload_blob(b"lock", overwrite=True)
        try:
            return bc.acquire_lease(lease_duration=60), bc  # renewed by renew_lock()
        except HttpResponseError as e:
            raise LockHeld(str(e))

    def renew_lock(self, handle):
        handle[0].renew()

    def release_lock(self, handle):
        try:
            handle[0].release()
        except Exception:
            pass


def make_storage(settings):
    if settings.storage == "azure":
        return AzureBlobStorage(settings.azure_account_url, settings.azure_container)
    return LocalStorage(settings.output_dir)


def publish_latest(storage, job: str, run_id: str, products_json: str, report: dict):
    """Called ONLY after validation passes. Report written last = commit marker."""
    storage.write_text(f"latest/{job}/products.json", products_json)
    storage.write_text(f"latest/{job}/report.json", json.dumps(report, indent=2))
