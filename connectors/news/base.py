"""Shared data models for news connectors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class NewsItem:
    title: str
    url: str
    summary: str
    source: str
    published_at: datetime
