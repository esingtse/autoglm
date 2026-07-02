"""Knowledge base memory for the Phone Agent.

Stores game-specific UI knowledge, workflow experience, and common trap patterns
across task runs so the agent gets smarter over time.

Usage:
    from phone_agent.memory import MemoryManager

    memory = MemoryManager()
    knowledge_prompt = memory.retrieve(task="打开和平精英，采集活动信息")
    # Inject knowledge_prompt into system prompt before agent.run()
    # After task completes:
    memory.learn(task="...", result="...")
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Knowledge entry types
# ---------------------------------------------------------------------------

ENTRY_TYPES = {
    "ui_layout": "UI 布局",
    "trap": "常见陷阱",
    "workflow": "操作流程",
    "popup_handling": "弹窗处理",
    "general": "通用经验",
}


# ---------------------------------------------------------------------------
# Game name list for extraction
# ---------------------------------------------------------------------------

# Extended from skills.py trigger keywords
KNOWN_GAMES: list[str] = [
    "和平精英",
    "王者荣耀",
    "蛋仔派对",
    "小小蚁国",
    "破晓的曙光",
    "完美世界：诸神之战",
    "三角洲行动",
    "原神",
    "崩坏：星穹铁道",
    "明日方舟",
    "英雄联盟手游",
    "金铲铲之战",
    "光遇",
    "第五人格",
    "梦幻西游",
    "阴阳师",
    "火影忍者",
    "QQ飞车",
    "穿越火线：枪战王者",
    "使命召唤手游",
]


# ---------------------------------------------------------------------------
# KnowledgeEntry
# ---------------------------------------------------------------------------


@dataclass
class KnowledgeEntry:
    """A single piece of knowledge."""

    id: str
    type: str  # ui_layout | trap | workflow | popup_handling | general
    key: str  # Short title / summary
    value: str  # Detailed knowledge content
    context: str  # When this knowledge applies
    confidence: float  # 0.0 - 1.0
    created_at: float  # Unix timestamp
    updated_at: float  # Unix timestamp
    success_count: int  # Times verified/used successfully
    source: str  # "auto" | "manual"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "key": self.key,
            "value": self.value,
            "context": self.context,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "success_count": self.success_count,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeEntry:
        return cls(
            id=data.get("id", ""),
            type=data.get("type", "general"),
            key=data.get("key", ""),
            value=data.get("value", ""),
            context=data.get("context", ""),
            confidence=data.get("confidence", 0.5),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            success_count=data.get("success_count", 0),
            source=data.get("source", "auto"),
        )

    @staticmethod
    def generate_id(key: str, value: str) -> str:
        """Generate a stable id from key and value content."""
        raw = f"{key}||{value}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# KnowledgeBase
# ---------------------------------------------------------------------------


class KnowledgeBase:
    """In-memory knowledge base for a single game."""

    def __init__(self, game: str = ""):
        self.game = game
        self.entries: list[KnowledgeEntry] = []
        self._id_index: dict[str, int] = {}  # entry_id -> list index

    def add(self, entry: KnowledgeEntry) -> KnowledgeEntry:
        """Add or update an entry. If key already exists, update in-place."""
        # De-duplicate by key similarity (same key string)
        for i, existing in enumerate(self.entries):
            if existing.key.strip() == entry.key.strip():
                # Update existing
                existing.value = entry.value
                existing.context = entry.context
                existing.confidence = max(existing.confidence, entry.confidence)
                existing.updated_at = time.time()
                existing.success_count += 1
                existing.source = entry.source
                return existing

        # New entry
        if not entry.id:
            entry.id = KnowledgeEntry.generate_id(entry.key, entry.value)
        if not entry.created_at:
            entry.created_at = time.time()
        if not entry.updated_at:
            entry.updated_at = time.time()

        self.entries.append(entry)
        self._id_index[entry.id] = len(self.entries) - 1
        return entry

    def remove(self, entry_id: str) -> bool:
        """Remove an entry by id."""
        if entry_id in self._id_index:
            idx = self._id_index.pop(entry_id)
            self.entries.pop(idx)
            # Rebuild index
            self._id_index = {e.id: i for i, e in enumerate(self.entries)}
            return True
        return False

    def update(self, entry_id: str, **kwargs: Any) -> bool:
        """Update fields of an existing entry."""
        if entry_id not in self._id_index:
            return False
        entry = self.entries[self._id_index[entry_id]]
        for key, value in kwargs.items():
            if hasattr(entry, key):
                setattr(entry, key, value)
        entry.updated_at = time.time()
        return True

    def search(
        self,
        query: str = "",
        entry_type: str | None = None,
        min_confidence: float = 0.3,
        limit: int = 10,
    ) -> list[KnowledgeEntry]:
        """Search entries by query text, type filter, and confidence threshold.

        Returns entries sorted by relevance (confidence * log(success_count + 1)).
        """
        query_lower = query.lower()

        scored: list[tuple[float, KnowledgeEntry]] = []
        for entry in self.entries:
            if entry.confidence < min_confidence:
                continue
            if entry_type and entry.type != entry_type:
                continue

            # Score: confidence * log(success_count + 1) + text match bonus
            score = entry.confidence * (entry.success_count + 1)
            if query_lower:
                # Bonus for matching key, value, or context
                if query_lower in entry.key.lower():
                    score *= 2.0
                if query_lower in entry.value.lower():
                    score *= 1.5
                if query_lower in entry.context.lower():
                    score *= 1.2

            scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "game": self.game,
            "version": 1,
            "updated_at": time.time(),
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeBase:
        kb = cls(game=data.get("game", ""))
        for entry_data in data.get("entries", []):
            entry = KnowledgeEntry.from_dict(entry_data)
            kb.entries.append(entry)
            kb._id_index[entry.id] = len(kb.entries) - 1
        return kb

    def save(self, filepath: str) -> None:
        """Persist knowledge base to a JSON file."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        data = self.to_dict()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, filepath: str) -> KnowledgeBase | None:
        """Load knowledge base from a JSON file. Returns None if not found."""
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def __len__(self) -> int:
        return len(self.entries)

    def __repr__(self) -> str:
        return f"KnowledgeBase(game={self.game!r}, entries={len(self.entries)})"


# ---------------------------------------------------------------------------
# MemoryManager
# ---------------------------------------------------------------------------


class MemoryManager:
    """Global memory manager for Phone Agent.

    Orchestrates knowledge retrieval and learning across multiple games.
    """

    def __init__(self, storage_dir: str | None = None):
        if storage_dir is None:
            storage_dir = os.path.join(
                os.path.expanduser("~"), ".phone_agent", "memory"
            )
        self.storage_dir = os.path.expanduser(storage_dir)
        self._cache: dict[str, KnowledgeBase] = {}

    # ---- Public API --------------------------------------------------------

    def retrieve(
        self, task: str, game: str | None = None, limit: int = 5
    ) -> str:
        """Retrieve relevant knowledge as a prompt-ready string.

        Args:
            task: The user's task description.
            game: Optional game name override. If None, extracted from task.
            limit: Max knowledge entries to include.

        Returns:
            A string to append to the system prompt, or empty string.
        """
        if game is None:
            game = self._extract_game(task)

        if not game:
            return ""

        kb = self._get_kb(game)
        if not kb or len(kb) == 0:
            return ""

        entries = kb.search(query=task, min_confidence=0.3, limit=limit)
        if not entries:
            return ""

        return self._build_prompt(entries, game)

    def learn(
        self,
        task: str,
        notes: list[str] | str,
        game: str | None = None,
        source: str = "auto",
    ) -> None:
        """Learn from a completed task.

        Args:
            task: The original task description.
            notes: Structured notes (list of strings) or a single summary string
                   from the agent's finish message.
            game: Optional game name override.
            source: "auto" for auto-extracted, "manual" for user-provided.
        """
        if game is None:
            game = self._extract_game(task)

        if not game:
            return

        kb = self._get_or_create_kb(game)

        if isinstance(notes, str):
            notes = [notes]

        for note in notes:
            if not note or not note.strip():
                continue
            note = note.strip()
            entry = self._parse_note_to_entry(note, source)
            if entry:
                kb.add(entry)

        self._save_kb(game, kb)

    def learn_manual(
        self,
        game: str,
        key: str,
        value: str,
        entry_type: str = "general",
        context: str = "",
    ) -> KnowledgeEntry:
        """Add a knowledge entry manually (high confidence, 'manual' source).

        Args:
            game: Game name.
            key: Short knowledge title.
            value: Detailed knowledge content.
            entry_type: Type of knowledge.
            context: When this knowledge applies.

        Returns:
            The created or updated KnowledgeEntry.
        """
        kb = self._get_or_create_kb(game)
        entry = KnowledgeEntry(
            id=KnowledgeEntry.generate_id(key, value),
            type=entry_type if entry_type in ENTRY_TYPES else "general",
            key=key,
            value=value,
            context=context,
            confidence=1.0,
            created_at=time.time(),
            updated_at=time.time(),
            success_count=1,
            source="manual",
        )
        result = kb.add(entry)
        self._save_kb(game, kb)
        return result

    def get_kb(self, game: str) -> KnowledgeBase | None:
        """Get a game's knowledge base (loaded from disk if needed)."""
        return self._get_kb(game)

    def list_games(self) -> list[str]:
        """List all games that have knowledge stored."""
        if not os.path.exists(self.storage_dir):
            return []
        games = []
        for fname in os.listdir(self.storage_dir):
            if fname.endswith(".json"):
                games.append(fname[:-5])
        return sorted(games)

    # ---- Internal helpers --------------------------------------------------

    def _get_kb(self, game: str) -> KnowledgeBase | None:
        """Get cached or load knowledge base for a game."""
        if game in self._cache:
            return self._cache[game]

        safe_name = self._safe_filename(game)
        filepath = os.path.join(self.storage_dir, f"{safe_name}.json")
        kb = KnowledgeBase.load(filepath)
        if kb:
            self._cache[game] = kb
        return kb

    def _get_or_create_kb(self, game: str) -> KnowledgeBase:
        """Get or create a knowledge base."""
        kb = self._get_kb(game)
        if kb is None:
            kb = KnowledgeBase(game=game)
            self._cache[game] = kb
        return kb

    def _save_kb(self, game: str, kb: KnowledgeBase) -> None:
        """Persist knowledge base to disk."""
        safe_name = self._safe_filename(game)
        filepath = os.path.join(self.storage_dir, f"{safe_name}.json")
        kb.save(filepath)

    def _build_prompt(self, entries: list[KnowledgeEntry], game: str) -> str:
        """Build a prompt string from knowledge entries."""
        lines = [
            "",
            "---",
            f"【关于《{game}》的历史经验】",
            "以下是从之前的操作中积累的知识，请优先参考：",
            "",
        ]
        for i, entry in enumerate(entries, 1):
            type_label = ENTRY_TYPES.get(entry.type, entry.type)
            lines.append(f"{i}. [{type_label}] {entry.key}")
            lines.append(f"   {entry.value}")
            if entry.context:
                lines.append(f"   适用场景: {entry.context}")
            lines.append("")
        lines.append("请结合以上经验执行任务，但注意实际界面可能有所变化。")
        lines.append("---")
        return "\n".join(lines)

    def _extract_game(self, task: str) -> str | None:
        """Extract game name from task text."""
        for game in KNOWN_GAMES:
            if game in task:
                return game
        # Try partial match for long names
        for game in KNOWN_GAMES:
            # Check first 2 chars match as substring
            if len(game) >= 2 and game[:2] in task:
                return game
        return None

    def _parse_note_to_entry(
        self, note: str, source: str = "auto"
    ) -> KnowledgeEntry | None:
        """Parse a text note into a knowledge entry."""
        note = note.strip()
        if not note or len(note) < 5:
            return None

        # Skip notes that look like structured event data
        if note.startswith("{") and note.endswith("}"):
            # This is likely a ResultCollector event record, not knowledge
            return None

        # Use first line or first 40 chars as key
        lines = note.split("\n")
        key = lines[0].strip()
        if len(key) > 60:
            key = key[:60] + "..."

        # Determine type heuristically
        entry_type = self._classify_note(key, note)

        entry_id = KnowledgeEntry.generate_id(key, note)

        return KnowledgeEntry(
            id=entry_id,
            type=entry_type,
            key=key,
            value=note,
            context="",
            confidence=0.5,
            created_at=time.time(),
            updated_at=time.time(),
            success_count=1,
            source=source,
        )

    @staticmethod
    def _classify_note(key: str, full_text: str) -> str:
        """Heuristically classify a note's type."""
        text = key + full_text
        if any(w in text for w in ["入口", "按钮", "位置", "坐标", "界面", "布局", "右下角", "左上角", "底部", "顶部"]):
            return "ui_layout"
        if any(w in text for w in ["误判", "误认为", "陷阱", "不要关闭", "不要跳过", "不是弹窗", "不是公告"]):
            return "trap"
        if any(w in text for w in ["提示框", "权限请求", "系统通知", "更新提示", "公告弹窗", "开屏公告", "同意", "弹窗处理", "处理弹窗"]):
            return "popup_handling"
        if any(w in text for w in ["流程", "步骤", "顺序", "遍历", "逐个", "先", "再", "然后"]):
            return "workflow"
        if any(w in text for w in ["关闭", "跳过", "弹窗"]):
            return "popup_handling"
        return "general"

    @staticmethod
    def _safe_filename(game: str) -> str:
        """Convert game name to safe filename."""
        # Replace special chars with underscore
        safe = game.replace("：", "_").replace(":", "_")
        safe = safe.replace(" ", "_")
        safe = safe.replace("/", "_").replace("\\", "_")
        return safe
