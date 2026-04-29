"""Structured result collection for event crawling tasks."""

from __future__ import annotations

import ast
import json
import re
import time
from dataclasses import asdict, dataclass
from typing import Any

from phone_agent.config.apps import get_package_name as get_android_package_name
from phone_agent.config.apps_harmonyos import get_package_name as get_harmony_package_name
from phone_agent.config.apps_ios import get_bundle_id as get_ios_bundle_id


@dataclass
class EventRecord:
    """Structured event record returned to the caller."""

    app_id: str
    package: str
    app_name: str
    title: str
    content: str
    reward: str
    event_date: str
    ts_crawl: int


class ResultCollector:
    """Collect and serialize structured event records."""

    def __init__(self, platform: str = "android"):
        self.platform = platform
        self._current_app: str = ""
        self._records: list[EventRecord] = []
        self._dedupe_keys: set[tuple[str, str, str, str]] = set()

    def reset(self) -> None:
        """Reset collector state for a new task."""
        self._current_app = ""
        self._records = []
        self._dedupe_keys = set()

    def set_current_app(self, app_name: str | None) -> None:
        """Update the current app context."""
        self._current_app = (app_name or "").strip()

    @property
    def records(self) -> list[EventRecord]:
        """Get a copy of collected records."""
        return list(self._records)

    @property
    def has_records(self) -> bool:
        """Whether any records have been collected."""
        return bool(self._records)

    def add_note(
        self, payload: str | dict[str, Any], current_app: str | None = None
    ) -> tuple[bool, str | None]:
        """Parse and store a structured note payload."""
        note_data = self._coerce_note_payload(payload)
        if note_data is None:
            return False, "Invalid Note payload: expected a JSON/object-like record"

        app_name = self._normalize_text(
            note_data.get("app_name") or current_app or self._current_app
        )
        package = self._normalize_text(
            note_data.get("package") or self._resolve_package(app_name)
        )
        app_id = self._normalize_text(note_data.get("app_id") or package or app_name)
        title = self._normalize_text(note_data.get("title"))
        content = self._normalize_text(note_data.get("content"))
        reward = self._normalize_text(note_data.get("reward")) or "无奖励"
        event_date = self._normalize_event_date(note_data.get("event_date"))
        ts_crawl = int(time.time())

        if not title:
            return False, "Invalid Note payload: missing title"

        record = EventRecord(
            app_id=app_id,
            package=package,
            app_name=app_name,
            title=title,
            content=content,
            reward=reward,
            event_date=event_date,
            ts_crawl=ts_crawl,
        )

        dedupe_key = (
            record.app_id,
            record.title,
            record.event_date,
            record.content,
        )
        if dedupe_key not in self._dedupe_keys:
            self._records.append(record)
            self._dedupe_keys.add(dedupe_key)

        return True, None

    def to_json(self, indent: int = 2) -> str:
        """Serialize collected records as a JSON array string."""
        return json.dumps(
            [asdict(record) for record in self._records],
            ensure_ascii=False,
            indent=indent,
        )

    def _resolve_package(self, app_name: str) -> str:
        """Resolve package/bundle name from the app name and platform."""
        if not app_name:
            return ""

        if self.platform == "ios":
            return get_ios_bundle_id(app_name) or ""
        if self.platform == "harmony":
            return get_harmony_package_name(app_name) or ""
        return get_android_package_name(app_name) or ""

    @staticmethod
    def _normalize_text(value: Any) -> str:
        """Normalize arbitrary values into stripped strings."""
        if value is None:
            return ""
        text = str(value).strip()
        if text.lower() in {"none", "null"}:
            return ""
        return text

    @staticmethod
    def _normalize_event_date(value: Any) -> str:
        """Normalize event date to YYYY-MM-DD when possible."""
        text = ResultCollector._normalize_text(value)
        if not text:
            return ""

        match = re.search(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
        if match:
            year, month, day = match.groups()
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        return ""

    @staticmethod
    def _coerce_note_payload(payload: str | dict[str, Any]) -> dict[str, Any] | None:
        """Parse a note payload from JSON or Python-literal-like text."""
        if isinstance(payload, dict):
            return payload

        text = str(payload).strip()
        if not text or text in {"True", "False"}:
            return None

        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(text)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue

        return None
