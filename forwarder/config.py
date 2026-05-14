from pathlib import Path
from typing import Optional

from pydantic import BeforeValidator, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Annotated


def _empty_to_none(v):
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


OptionalInt = Annotated[Optional[int], BeforeValidator(_empty_to_none)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    # LocalSend (only consumed by entrypoint.sh, listed here for documentation)
    localsend_alias: str = "Paperless Inbox"
    localsend_pin: str = ""

    # Filesystem
    incoming_dir: Path = Path("/data/incoming")
    retry_dir: Path = Path("/data/retry")
    watcher_debounce_seconds: float = 2.0

    # Paperless
    paperless_url: str = Field(..., min_length=1)
    paperless_token: str = Field(..., min_length=1)
    paperless_verify_ssl: bool = True

    paperless_default_tags: str = ""           # comma-separated IDs
    paperless_default_correspondent: OptionalInt = None
    paperless_default_document_type: OptionalInt = None
    paperless_default_storage_path: OptionalInt = None
    paperless_title_prefix: str = ""

    paperless_poll_task: bool = True
    paperless_poll_timeout_seconds: float = 60.0
    paperless_poll_interval_seconds: float = 2.0

    # Retry
    retry_interval_seconds: float = 300.0

    # Logging
    log_level: str = "INFO"

    @field_validator("paperless_url")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @property
    def default_tag_ids(self) -> list[int]:
        return [int(t) for t in self.paperless_default_tags.split(",") if t.strip()]


settings = Settings()
