"""Configuration management."""

from dataclasses import dataclass


@dataclass
class AppConfig:
    """Root application configuration."""

    database_path: str = ""
