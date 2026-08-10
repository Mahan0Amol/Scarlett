"""
Structured half of the memory plugin: named categories holding named items
(phone numbers, addresses, folder paths, emails, credentials, ...) where the
user or model wants to address a specific value by name later.

This is a near-verbatim carry-over of the old plugins/items/plugin.py
ItemAgent - that code's atomic-write/backup/case-insensitive-lookup logic
was solid, so it's reused rather than rewritten. Only the class name, the
default data file, and the default seed category changed.
"""

import json
import os
import shutil
import asyncio
from pathlib import Path


class ItemStore:
    def __init__(self, data_file_path: str = "structured_data.json"):
        # Resolve relative paths against this file's directory, not the
        # process's current working directory, so this works no matter
        # where Scarlett.py is launched from. Absolute paths are left as-is.
        p = Path(data_file_path)
        if not p.is_absolute():
            p = (Path(__file__).resolve().parent / p).resolve()
        self.data_file_path = str(p)

        # Backups live next to the data file.
        self._backup_path = str(p.with_suffix(p.suffix + ".bak"))

        # Guards concurrent read-modify-write cycles. Without this, two
        # function calls arriving close together (very possible in an
        # async agent) can clobber each other's changes.
        self._lock = asyncio.Lock()

        self._seed_if_missing()

    def _seed_if_missing(self):
        if not Path(self.data_file_path).exists():
            seed = {
                "contacts": {"description": "Phone numbers, emails, and other contact info.", "items": {}},
                "places": {"description": "Addresses, folder paths, and other locations.", "items": {}},
            }
            Path(self.data_file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.data_file_path, "w", encoding="utf-8") as f:
                json.dump(seed, f, indent=4, ensure_ascii=False)

    # ─────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────

    async def _load(self) -> dict:
        """Load and return the full JSON data from disk."""
        try:
            with open(self.data_file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"[ItemStore] File not found: {self.data_file_path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"[ItemStore] JSON decode error: {e}")
            return {}

    async def _save(self, data: dict) -> bool:
        """
        Atomically write data back to disk. Returns True on success.

        Writes to a temp file first and then swaps it into place with
        os.replace(), so a crash or power loss mid-write can never leave
        the data file half-written / corrupted. Also keeps a single-file
        backup of the previous version before swapping.
        """
        target = Path(self.data_file_path)
        tmp_path = target.with_suffix(target.suffix + ".tmp")

        try:
            target.parent.mkdir(parents=True, exist_ok=True)

            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            if target.exists():
                try:
                    shutil.copyfile(target, self._backup_path)
                except OSError as e:
                    print(f"[ItemStore] Warning: could not write backup: {e}")

            os.replace(tmp_path, target)  # atomic on POSIX and Windows
            return True
        except (IOError, OSError) as e:
            print(f"[ItemStore] Failed to save file: {e}")
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            return False

    @staticmethod
    def _find_key_ci(d: dict, name: str):
        """
        Find the actual key in `d` matching `name` case-insensitively.
        Returns the real key (preserving original casing) or None.
        Prefers an exact match if one exists.
        """
        if name in d:
            return name
        name_lower = name.strip().lower()
        for key in d:
            if key.strip().lower() == name_lower:
                return key
        return None

    @staticmethod
    def _clean(value):
        return value.strip() if isinstance(value, str) else value

    # ─────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────

    async def read_categories(self) -> str:
        data = await self._load()
        summary = {name: cat.get("description", "") for name, cat in data.items()}
        return f"Categories (with descriptions): {json.dumps(summary, ensure_ascii=False, indent=2)}"

    async def read_category_items(self, category_name: str) -> str:
        category_name = self._clean(category_name)
        data = await self._load()

        real_category = self._find_key_ci(data, category_name)
        if real_category is None:
            return f"Category '{category_name}' not found."

        description = data[real_category].get("description", "")
        items = data[real_category].get("items", {})

        if not items:
            return f"Category '{real_category}' (description: '{description}') exists but has no items."
        return (
            f"Category '{real_category}' (description: '{description}'). "
            f"Items: {json.dumps(items, ensure_ascii=False, indent=2)}"
        )

    async def add_category(self, category_name: str, description: str) -> str:
        category_name = self._clean(category_name)
        if not category_name:
            return "Category name cannot be empty."

        async with self._lock:
            data = await self._load()
            if self._find_key_ci(data, category_name) is not None:
                return f"Category '{category_name}' already exists."

            data[category_name] = {"description": description, "items": {}}
            if await self._save(data):
                return f"Category '{category_name}' added successfully."
            return f"Error adding category '{category_name}': failed to save data to disk."

    async def item_exists(self, category_name: str, item_name: str) -> bool:
        data = await self._load()
        category_name = self._clean(category_name)
        item_name = self._clean(item_name)

        real_category = self._find_key_ci(data, category_name)
        if real_category is None:
            return False
        items = data[real_category].get("items", {})
        return self._find_key_ci(items, item_name) is not None

    async def add_item(self, category_name: str, item_name: str, value: str) -> str:
        category_name = self._clean(category_name)
        item_name = self._clean(item_name)
        if not category_name or not item_name:
            return "Category name and item name cannot be empty."

        async with self._lock:
            data = await self._load()
            real_category = self._find_key_ci(data, category_name)
            if real_category is None:
                return f"Category '{category_name}' not found."

            items = data[real_category].setdefault("items", {})
            if self._find_key_ci(items, item_name) is not None:
                return f"Item '{item_name}' already exists in '{real_category}'."

            items[item_name] = {"value": value}
            if await self._save(data):
                return f"Item '{item_name}' added to category '{real_category}' successfully."
            return f"Error adding item '{item_name}' to category '{real_category}': failed to save data to disk."

    async def search_item(self, query: str) -> str:
        data = await self._load()
        query_lower = query.lower()
        results = []

        for category_name, category_data in data.items():
            items = category_data.get("items", {})
            for item_name, item_data in items.items():
                value = str(item_data.get("value", ""))
                if query_lower in item_name.lower() or query_lower in value.lower():
                    results.append({"category": category_name, "item_name": item_name, "value": value})

        if not results:
            return f"No items found matching '{query}'."
        return f"Search results for '{query}': {json.dumps(results, ensure_ascii=False, indent=2)}"

    async def update_item(self, category_name: str, item_name: str, new_value: str) -> str:
        category_name = self._clean(category_name)
        item_name = self._clean(item_name)

        async with self._lock:
            data = await self._load()
            real_category = self._find_key_ci(data, category_name)
            if real_category is None:
                return f"Category '{category_name}' not found."

            items = data[real_category].get("items", {})
            real_item = self._find_key_ci(items, item_name)
            if real_item is None:
                return f"Item '{item_name}' not found in '{real_category}'."

            items[real_item]["value"] = new_value
            if await self._save(data):
                return f"Item '{real_item}' updated successfully."
            return f"Error updating item '{real_item}': failed to save data to disk."

    async def remove_item(self, category_name: str, item_name: str) -> str:
        category_name = self._clean(category_name)
        item_name = self._clean(item_name)

        async with self._lock:
            data = await self._load()
            real_category = self._find_key_ci(data, category_name)
            if real_category is None:
                return f"Category '{category_name}' not found."

            items = data[real_category].get("items", {})
            real_item = self._find_key_ci(items, item_name)
            if real_item is None:
                return f"Item '{item_name}' not found in '{real_category}'."

            del items[real_item]
            if await self._save(data):
                return f"Item '{real_item}' removed from '{real_category}'."
            return f"Error removing item '{real_item}': failed to save data to disk."
