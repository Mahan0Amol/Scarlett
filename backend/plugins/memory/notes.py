"""
Free-text half of the memory plugin: small, curated .md files (USER.md,
AGENT.md, or whatever the model names) that get folded into the session's
system prompt at connect time - the same role SOUL.md/USER.md play for
Hermes, or a memory-file directory for Claude.

These are NOT a general-purpose database. They're meant to stay small and
always-relevant (persona notes, a handful of durable facts about the user) -
structured, addressable, or high-volume data belongs in ItemStore instead.
A per-file size cap enforces that: once a file is full, writes are refused
with a message telling the model to trim it, rather than silently growing
the context every session forever.
"""

from pathlib import Path
from typing import List

MAX_NOTE_BYTES = 4000  # keeps any one file's contribution to system_instruction small


class NoteStore:
    def __init__(self, notes_dir: str):
        self.notes_dir = Path(notes_dir)
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        # Seed the two conventional files so they always exist and are
        # listed, even before anything's been written to them.
        for default_name, header in (
            ("USER.md", "# User\n\nDurable facts and preferences about the user.\n"),
            ("AGENT.md", "# Agent\n\nNotes Scarlett has made for herself (habits to follow, past decisions).\n"),
        ):
            path = self.notes_dir / default_name
            if not path.exists():
                path.write_text(header, encoding="utf-8")

    def _resolve(self, name: str) -> Path:
        # Only bare filenames inside notes_dir - block path traversal and
        # accidental writes outside the notes folder.
        safe_name = Path(name).name
        if not safe_name.endswith(".md"):
            safe_name += ".md"
        return self.notes_dir / safe_name

    def list_notes(self) -> List[str]:
        return sorted(p.name for p in self.notes_dir.glob("*.md"))

    def read(self, name: str) -> str:
        path = self._resolve(name)
        if not path.exists():
            return f"No note named '{path.name}' yet."
        return path.read_text(encoding="utf-8")

    def write(self, name: str, content: str) -> str:
        """Overwrites a note entirely."""
        if len(content.encode("utf-8")) > MAX_NOTE_BYTES:
            return (
                f"'{name}' would be {len(content.encode('utf-8'))} bytes, over the "
                f"{MAX_NOTE_BYTES}-byte cap for a system-prompt file. Trim it, or use "
                f"add_item for data that doesn't need to be in every session's context."
            )
        path = self._resolve(name)
        path.write_text(content, encoding="utf-8")
        return f"Wrote '{path.name}' ({len(content.encode('utf-8'))} bytes)."

    def append(self, name: str, line: str) -> str:
        path = self._resolve(name)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        new_content = existing.rstrip("\n") + "\n" + line.strip() + "\n"
        if len(new_content.encode("utf-8")) > MAX_NOTE_BYTES:
            return (
                f"Can't append - '{path.name}' is at its {MAX_NOTE_BYTES}-byte cap. "
                f"Summarize/trim it first with write_note, or use add_item instead."
            )
        path.write_text(new_content, encoding="utf-8")
        return f"Appended to '{path.name}'."

    def get_system_prompt_context(self, names: List[str] = ("USER.md", "AGENT.md")) -> str:
        """
        Called once at session start (from Scarlett.py, not by the model)
        to build the block that gets injected via notify_model(). Reads
        only the conventional files by default, capped total, so a session
        never pulls in every note the model has ever written.
        """
        blocks = []
        for name in names:
            path = self._resolve(name)
            if path.exists():
                text = path.read_text(encoding="utf-8").strip()
                if text:
                    blocks.append(f"--- {path.name} ---\n{text}")
        return "\n\n".join(blocks)
