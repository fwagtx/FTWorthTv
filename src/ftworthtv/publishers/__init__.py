from __future__ import annotations

from pathlib import Path

from ..config import Settings
from .base import Publisher
from .dryrun import DryRunPublisher


def get_publisher(name: str, settings: Settings, run_dir: Path) -> Publisher:
    name = (name or "dryrun").lower()
    if name == "dryrun" or settings.dry_run:
        return DryRunPublisher(settings, run_dir)
    if name == "facebook":
        from .facebook import FacebookPublisher
        return FacebookPublisher(settings)
    if name == "metricool":
        from .metricool import MetricoolPublisher
        return MetricoolPublisher(settings)
    raise ValueError(f"unknown publisher {name!r} (use dryrun, facebook or metricool)")
