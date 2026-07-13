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


# ---------------------------------------------------------------------------
# Activity Summary Parser
# ---------------------------------------------------------------------------


@dataclass
class ActivityItem:
    """A single parsed activity."""

    tab_name: str       # 所属标签名称，如 "活动"、"资讯"
    title: str          # 活动名称
    time: str           # 活动时间
    rules: str          # 参与规则
    reward: str         # 奖励内容


def parse_activity_summary(text: str) -> list[ActivityItem]:
    """Parse the Note summary format into structured ActivityItem objects.

    Expected format::

        === 活动汇总 ===

        【标签名 - 活动名称】
        活动时间：xxx
        规则：xxx
        奖励：xxx

    Returns a list of ActivityItem, one per activity block.
    """
    items: list[ActivityItem] = []

    # Remove the header line if present
    text = text.strip()
    if text.startswith("==="):
        # Find end of header
        idx = text.find("\n")
        if idx > 0:
            text = text[idx + 1 :].strip()

    # Split by 【...】 blocks
    # Pattern: 【标签 - 名称】\n活动时间：...\n规则：...\n奖励：...
    blocks = _split_activity_blocks(text)

    for block in blocks:
        item = _parse_single_activity(block)
        if item:
            items.append(item)

    return items


def parse_activity_summary_to_dict(text: str) -> list[dict[str, str]]:
    """Same as parse_activity_summary but returns plain dicts."""
    items = parse_activity_summary(text)
    return [
        {
            "tab_name": item.tab_name,
            "title": item.title,
            "time": item.time,
            "rules": item.rules,
            "reward": item.reward,
        }
        for item in items
    ]


def _split_activity_blocks(text: str) -> list[str]:
    """Split summary text into individual activity blocks."""
    blocks: list[str] = []
    current: list[str] = []
    in_block = False

    for line in text.split("\n"):
        stripped = line.strip()

        # Detect start of a new activity: 【...】
        if stripped.startswith("【") and "】" in stripped:
            if in_block and current:
                blocks.append("\n".join(current))
            current = [stripped]
            in_block = True
        elif in_block:
            # Empty line ends the current activity block
            if not stripped and current:
                # Don't end on empty lines between activities — look ahead
                pass
            current.append(stripped)

    # Don't forget the last block
    if current:
        blocks.append("\n".join(current))

    return blocks


def _parse_single_activity(block: str) -> ActivityItem | None:
    """Parse a single activity block like::

        【活动 - 荣耀跳高 领联名枪皮】
        活动时间：05.29-06.11
        规则：xxx
        奖励：xxx
    """
    lines = [l.strip() for l in block.split("\n") if l.strip()]
    if not lines:
        return None

    # First line: 【标签 - 名称】
    header = lines[0]
    tab_name = ""
    title = ""

    # Match 【xxx - yyy】 or 【xxx】
    match = re.match(r"【(.+?)】", header)
    if match:
        content = match.group(1)
        if " - " in content:
            parts = content.split(" - ", 1)
            tab_name = parts[0].strip()
            title = parts[1].strip()
        else:
            tab_name = ""
            title = content.strip()

    if not title:
        return None

    # Parse key: value fields
    fields: dict[str, str] = {"time": "", "rules": "", "reward": ""}

    for line in lines[1:]:
        # Match "活动时间：xxx", "规则：xxx", "奖励：xxx"
        for key in ("活动时间", "时间", "规则", "奖励"):
            if line.startswith(key + "：") or line.startswith(key + ":"):
                _, value = re.split(r"[：:]", line, maxsplit=1)
                mapped_key = {
                    "活动时间": "time",
                    "时间": "time",
                    "规则": "rules",
                    "奖励": "reward",
                }[key]
                fields[mapped_key] = value.strip()
                break

    return ActivityItem(
        tab_name=tab_name,
        title=title,
        time=fields["time"],
        rules=fields["rules"],
        reward=fields["reward"],
    )


# ---------------------------------------------------------------------------
# Proto-compatible (GameEvent) conversion
# ---------------------------------------------------------------------------


def activity_summary_to_game_events(
    text: str,
    app_name: str = "",
    platform: str = "android",
) -> list[dict[str, object]]:
    """Parse Note summary and convert to proto-compatible GameEvent dicts.

    Field mapping (matching `message GameEvent`):
        app_id    ← package name
        package   ← resolved from app_name
        app_name  ← game name
        title     ← activity title
        content   ← tab label + rules combined
        reward    ← activity reward
       event_date← normalized YYYY-MM-DD (best effort)
       ts_crawl  ← current Unix timestamp
       start_date← normalized start date YYYY-MM-DD
       end_data  ← normalized end date YYYY-MM-DD

    Args:
        text: The Note summary text in ``=== 活动汇总 ===`` format.
        app_name: The game/app name (e.g. "和平精英").
        platform: Platform for package resolution ("android" / "ios" / "harmony").

    Returns:
        List of dicts matching the proto GameEvent structure.
    """
    from phone_agent.config.apps import get_package_name as get_android_package
    from phone_agent.config.apps_harmonyos import get_package_name as get_harmony_package
    from phone_agent.config.apps_ios import get_bundle_id as get_ios_package

    activities = parse_activity_summary(text)
    now_ts = int(time.time())

    # Resolve package
    if platform == "ios":
        package = get_ios_package(app_name) or ""
    elif platform == "harmony":
        package = get_harmony_package(app_name) or ""
    else:
        package = get_android_package(app_name) or ""

    results: list[dict[str, object]] = []
    for item in activities:
        # Parse start/end dates from the activity time string
        start_date, end_date = _normalize_date_range_for_proto(item.time)
        event_date = end_date or start_date

        # content = tab label context + rules
        content_parts = []
        if item.tab_name:
            content_parts.append(f"所属标签: {item.tab_name}")
        if item.rules:
            content_parts.append(f"规则: {item.rules}")
        if item.time:
            content_parts.append(f"活动时间: {item.time}")
        content = "; ".join(content_parts) if content_parts else ""

        results.append({
            "app_id": package,
            "package": package,
            "app_name": app_name,
            "title": item.title,
           "content": content,
            "reward": item.reward or "无奖励",
           "event_date": event_date,
            "start_date": start_date,
            "end_data": end_date,
            "ts_crawl": now_ts,
        })

    return results


def _normalize_date_range_for_proto(time_text: str) -> tuple[str, str]:
    """Parse a time string into (start_date, end_date) in YYYY-MM-DD format.

    Handles common patterns found in game activity time strings:
    - ``2026/5/29-2026/6/4`` → ("2026-05-29", "2026-06-04")
    - ``05.29-06.11`` → ("2026-05-29", "2026-06-11")
    - ``6月1日~6月30日`` → ("2026-06-01", "2026-06-30")
    - ``5月27日-6月9日`` → ("2026-05-27", "2026-06-09")
    - ``4月18日开启`` → ("2026-04-18", "")
    - ``长期有效`` / ``限时招募`` → ("", "")

    Returns:
        (start_date, end_date) tuple, either may be "" if not parseable.
    """
    if not time_text:
        return "", ""

    import datetime

    text = time_text.strip()
    cy = datetime.datetime.now().year

    # Pattern: YYYY/M/D-YYYY/M/D  (full range with years)
    m = re.search(
        r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})\s*[-~至到]\s*(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})",
        text,
    )
    if m:
        sy, sm, sd = int(m.group(1)), int(m.group(2)), int(m.group(3))
        ey, em, ed = int(m.group(4)), int(m.group(5)), int(m.group(6))
        return f"{sy:04d}-{sm:02d}-{sd:02d}", f"{ey:04d}-{em:02d}-{ed:02d}"

    # Pattern: M.D-M.D or M/D-M/D (no year) e.g. "05.29-06.11", "7/10-8/10"
    m = re.search(
        r"(\d{1,2})[./](\d{1,2})\s*[-~至到]\s*(\d{1,2})[./](\d{1,2})", text
    )
    if m:
        sm, sd = int(m.group(1)), int(m.group(2))
        em, ed = int(m.group(3)), int(m.group(4))
        return f"{cy:04d}-{sm:02d}-{sd:02d}", f"{cy:04d}-{em:02d}-{ed:02d}"

    # Pattern: M月D日~M月D日 or M月D日-M月D日
    m = re.search(
        r"(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*[-~至到]\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        text,
    )
    if m:
        sm, sd = int(m.group(1)), int(m.group(2))
        em, ed = int(m.group(3)), int(m.group(4))
        return f"{cy:04d}-{sm:02d}-{sd:02d}", f"{cy:04d}-{em:02d}-{ed:02d}"

    # Pattern: single YYYY/M/D
    m = re.search(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}", ""

    # Pattern: "4月18日开启" — single start date
    m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日.*开启", text)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        return f"{cy:04d}-{mo:02d}-{d:02d}", ""

    # Pattern: single "M月D日"
    m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        return f"{cy:04d}-{mo:02d}-{d:02d}", ""

    # Pattern: single M.D or M/D (no year, no range)
    m = re.search(r"(\d{1,2})[./](\d{1,2})", text)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        return f"{cy:04d}-{mo:02d}-{d:02d}", ""

    return "", ""


def _normalize_event_date_for_proto(time_text: str) -> str:
    """Return the end date (or start if no end) in YYYY-MM-DD format.

    Thin wrapper around :func:`_normalize_date_range_for_proto` for callers
    that only need a single date string.
    """
    start, end = _normalize_date_range_for_proto(time_text)
    return end or start
