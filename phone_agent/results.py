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
    time: str           # 活动时间（旧格式：整段范围文本）
    rules: str          # 参与规则
    reward: str         # 奖励内容
    start_time: str = ""   # 活动起始时间（新格式：单日期）
    end_time: str = ""     # 活动结束时间（新格式：单日期）


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
            "start_time": item.start_time,
            "end_time": item.end_time,
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
    fields: dict[str, str] = {
        "time": "",
        "rules": "",
        "reward": "",
        "start_time": "",
        "end_time": "",
    }

    for line in lines[1:]:
        # Match "活动时间：xxx", "活动起始时间：xxx", "活动结束时间：xxx",
        # "规则：xxx", "奖励：xxx". Longer keys are checked first so
        # "活动起始时间" wins over the "活动时间" prefix.
        for key in (
            "活动起始时间",
            "活动结束时间",
            "活动开始时间",
            "活动结束",
            "活动时间",
            "时间",
            "规则",
            "奖励",
        ):
            if line.startswith(key + "：") or line.startswith(key + ":"):
                _, value = re.split(r"[：:]", line, maxsplit=1)
                mapped_key = {
                    "活动起始时间": "start_time",
                    "活动开始时间": "start_time",
                    "活动结束时间": "end_time",
                    "活动结束": "end_time",
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
        start_time=fields["start_time"],
        end_time=fields["end_time"],
    )


# ---------------------------------------------------------------------------
# Proto-compatible (GameEvent) conversion
# ---------------------------------------------------------------------------


def _resolve_package(app_name: str, platform: str) -> str:
    """Resolve package/bundle name from app name and platform."""
    from phone_agent.config.apps import get_package_name as get_android_package
    from phone_agent.config.apps_harmonyos import get_package_name as get_harmony_package
    from phone_agent.config.apps_ios import get_bundle_id as get_ios_package

    if platform == "ios":
        return get_ios_package(app_name) or ""
    if platform == "harmony":
        return get_harmony_package(app_name) or ""
    return get_android_package(app_name) or ""


def _activity_item_to_event(
    item: ActivityItem,
    app_name: str,
    package: str,
    now_ts: int,
    screenshot_path: str | None = None,
) -> dict[str, object]:
    """Convert a single parsed ActivityItem to a proto-compatible GameEvent dict.

    Date resolution: if the new per-boundary fields ``start_time`` / ``end_time``
    are present (single dates from the split Note format), they are normalized
    directly and win over the legacy combined ``time`` range string. Otherwise
    the combined ``time`` is parsed as a range via
    :func:`_normalize_date_range_for_proto` (which now also strips clock-time
    tokens like `` 00:00``).
    """
    if item.start_time or item.end_time:
        start_date = _normalize_single_date_for_proto(item.start_time)
        end_date = _normalize_single_date_for_proto(item.end_time)
    else:
        start_date, end_date = _normalize_date_range_for_proto(item.time)
    event_date = end_date or start_date

    content_parts = []
    if item.tab_name:
        content_parts.append(f"所属标签: {item.tab_name}")
    if item.rules:
        content_parts.append(f"规则: {item.rules}")
    if item.time:
        content_parts.append(f"活动时间: {item.time}")
    if item.start_time and not item.time:
        content_parts.append(f"活动起始时间: {item.start_time}")
    if item.end_time and not item.time:
        content_parts.append(f"活动结束时间: {item.end_time}")
    content = "; ".join(content_parts) if content_parts else ""

    event = {
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
    }
    if screenshot_path is not None:
        event["screenshot"] = screenshot_path
    return event


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
    activities = parse_activity_summary(text)
    now_ts = int(time.time())
    package = _resolve_package(app_name, platform)

    return [
        _activity_item_to_event(item, app_name, package, now_ts)
        for item in activities
    ]


def activity_notes_to_game_events(
    notes: list[dict[str, Any]],
    app_name: str = "",
    platform: str = "android",
) -> list[dict[str, object]]:
    """Parse per-activity Note records (with screenshot paths) into GameEvents.

    Each note dict has the shape ``{"message": str, "screenshot_path": str | None}``,
    where ``message`` is a single-activity block (``【标签 - 标题】`` + fields).
    Non-activity notes (parse to no ActivityItem) are skipped.

    Args:
        notes: List of ``{message, screenshot_path}`` dicts collected by the agent.
        app_name: The game/app name (e.g. "和平精英").
        platform: Platform for package resolution ("android" / "ios" / "harmony").

    Returns:
        List of GameEvent dicts; each carries a ``screenshot`` path when one was saved.
    """
    now_ts = int(time.time())
    package = _resolve_package(app_name, platform)

    results: list[dict[str, object]] = []
    for note in notes:
        message = note.get("message", "")
        screenshot_path = note.get("screenshot_path")
        activities = parse_activity_summary(message)
        for item in activities:
            results.append(
                _activity_item_to_event(
                    item, app_name, package, now_ts, screenshot_path
                )
            )
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
    # Strip clock-time tokens (e.g. " 00:00", " 23:59:30") so date-range
    # patterns like "07.10-07.30" match even when written as
    # "07.10 00:00-07.30 23:59". Only the time-of-day is removed; the date
    # portion is preserved. A leading space is kept so dates don't fuse.
    text = re.sub(r"\s*\d{1,2}:\d{2}(?::\d{2})?", " ", text)
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


def _normalize_single_date_for_proto(text: str) -> str:
    """Normalize a single date string to YYYY-MM-DD, ignoring any trailing time.

    Used for the new per-boundary Note fields (``活动起始时间`` / ``活动结束时间``),
    which are single dates but may still carry a clock-time suffix
    (e.g. ``07.30 23:59``). Returns ``""`` when no date is found.
    """
    start, _ = _normalize_date_range_for_proto(text)
    return start
