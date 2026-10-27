from dataclasses import dataclass
import os


DEFAULT_OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1"
DEFAULT_OPEN_METEO_ARCHIVE_BASE_URL = "https://archive-api.open-meteo.com/v1"
DEFAULT_HTTP_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class Settings:
    open_meteo_base_url: str = DEFAULT_OPEN_METEO_BASE_URL
    open_meteo_archive_base_url: str = DEFAULT_OPEN_METEO_ARCHIVE_BASE_URL
    http_timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            open_meteo_base_url=os.getenv(
                "OPEN_METEO_BASE_URL", DEFAULT_OPEN_METEO_BASE_URL
            ).rstrip("/"),
            open_meteo_archive_base_url=os.getenv(
                "OPEN_METEO_ARCHIVE_BASE_URL",
                DEFAULT_OPEN_METEO_ARCHIVE_BASE_URL,
            ).rstrip("/"),
            http_timeout_seconds=float(
                os.getenv("HTTP_TIMEOUT_SECONDS", str(DEFAULT_HTTP_TIMEOUT_SECONDS))
            ),
        )

