"""Thin Paperless-ngx REST client.

Endpoints used:
- POST /api/documents/post_document/   → enqueue document, returns task UUID
- GET  /api/tasks/?task_id=<uuid>      → poll task status
"""

import logging
import mimetypes
import time
from pathlib import Path

import httpx

from .config import settings

log = logging.getLogger(__name__)


class PaperlessError(RuntimeError):
    pass


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=settings.paperless_url,
        headers={"Authorization": f"Token {settings.paperless_token}"},
        verify=settings.paperless_verify_ssl,
        timeout=httpx.Timeout(30.0, read=120.0),
    )


def _build_form_data() -> dict:
    data: dict = {}
    if settings.paperless_default_correspondent is not None:
        data["correspondent"] = str(settings.paperless_default_correspondent)
    if settings.paperless_default_document_type is not None:
        data["document_type"] = str(settings.paperless_default_document_type)
    if settings.paperless_default_storage_path is not None:
        data["storage_path"] = str(settings.paperless_default_storage_path)
    tag_ids = settings.default_tag_ids
    if tag_ids:
        # httpx multipart sends one form field per list item with the same key.
        data["tags"] = [str(t) for t in tag_ids]
    return data


def post_document(file_path: Path) -> str | None:
    """Upload a file to Paperless. Returns task UUID (or None if Paperless
    did not return one — older instances may answer with a plain string).
    Raises PaperlessError on non-2xx responses.
    """
    title = f"{settings.paperless_title_prefix}{file_path.stem}".strip()
    mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"

    data = _build_form_data()
    if title:
        data["title"] = title

    with _client() as client, file_path.open("rb") as fh:
        files = {"document": (file_path.name, fh, mime)}
        resp = client.post("/api/documents/post_document/", data=data, files=files)

    if resp.status_code >= 300:
        raise PaperlessError(
            f"post_document HTTP {resp.status_code}: {resp.text[:500]}"
        )

    # Response is typically a JSON-quoted task UUID string, e.g. '"abc-123"'.
    body = resp.text.strip().strip('"')
    log.info("paperless accepted %s, task=%s", file_path.name, body or "<unknown>")
    return body or None


def poll_task(task_uuid: str) -> dict:
    """Poll /api/tasks/ until the task reaches a terminal state or times out.
    Returns the last task object. Raises PaperlessError on FAILURE.
    """
    deadline = time.monotonic() + settings.paperless_poll_timeout_seconds
    last: dict = {}
    with _client() as client:
        while time.monotonic() < deadline:
            resp = client.get("/api/tasks/", params={"task_id": task_uuid})
            if resp.status_code >= 300:
                raise PaperlessError(
                    f"poll HTTP {resp.status_code}: {resp.text[:500]}"
                )
            tasks = resp.json()
            if tasks:
                last = tasks[0]
                status = last.get("status")
                if status == "SUCCESS":
                    log.info("task %s: SUCCESS doc_id=%s",
                             task_uuid, last.get("related_document"))
                    return last
                if status == "FAILURE":
                    raise PaperlessError(
                        f"task {task_uuid} FAILURE: {last.get('result')}"
                    )
            time.sleep(settings.paperless_poll_interval_seconds)
    raise PaperlessError(
        f"task {task_uuid} did not finish within "
        f"{settings.paperless_poll_timeout_seconds}s (last={last.get('status')})"
    )


def forward(file_path: Path) -> None:
    """End-to-end: upload + optional task polling. Raises PaperlessError on failure."""
    task_uuid = post_document(file_path)
    if settings.paperless_poll_task and task_uuid:
        poll_task(task_uuid)
