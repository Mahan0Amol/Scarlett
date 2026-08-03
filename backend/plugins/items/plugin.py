import json
import os
import shutil
import asyncio
from pathlib import Path
from datetime import datetime


class ItemAgent:
    def __init__(self, items_file_path: str = "items.json"):
        # Resolve relative paths against this file's directory, not the
        # process's current working directory, so this works no matter
        # where Scarlett.py is launched from. Absolute paths are left as-is.
        p = Path(items_file_path)
        if not p.is_absolute():
            p = (Path(__file__).resolve().parent / p).resolve()
        self.items_file_path = str(p)

        # Backups live next to the data file.
        self._backup_path = str(p.with_suffix(p.suffix + ".bak"))

        # Guards concurrent read-modify-write cycles. Without this, two
        # function calls arriving close together (very possible in an
        # async agent) can clobber each other's changes.
        self._lock = asyncio.Lock()

    # ─────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────

    async def _load(self) -> dict:
        """Load and return the full JSON data from disk."""
        try:
            with open(self.items_file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"[ItemAgent] File not found: {self.items_file_path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"[ItemAgent] JSON decode error: {e}")
            return {}

    async def _save(self, data: dict) -> bool:
        """
        Atomically write data back to disk. Returns True on success.

        Writes to a temp file first and then swaps it into place with
        os.replace(), so a crash or power loss mid-write can never leave
        items.json half-written / corrupted. Also keeps a single-file
        backup of the previous version before swapping.
        """
        target = Path(self.items_file_path)
        tmp_path = target.with_suffix(target.suffix + ".tmp")

        try:
            target.parent.mkdir(parents=True, exist_ok=True)

            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            # Best-effort backup of the current file before we overwrite it.
            if target.exists():
                try:
                    shutil.copyfile(target, self._backup_path)
                except OSError as e:
                    print(f"[ItemAgent] Warning: could not write backup: {e}")

            os.replace(tmp_path, target)  # atomic on POSIX and Windows
            return True
        except (IOError, OSError) as e:
            print(f"[ItemAgent] Failed to save file: {e}")
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
    def _clean(value: str) -> str:
        """Basic input validation: strip whitespace."""
        return value.strip() if isinstance(value, str) else value

    # ─────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────

    async def read_categories(self, fc=None) -> str:
        """Return a list of all category names."""
        print(f"[ItemAgent] read_categories called with fc: {fc}")

        print(f"[ItemAgent] Reading categories from '{self.items_file_path}'")
        try:
            data = await self._load()
        except Exception as e:
            print(f"[ItemAgent] Error reading categories: {e}")
            return "Error reading categories."

        summary = {name: cat.get("description", "") for name, cat in data.items()}
        return f"The list of categories (with their descriptions) is: {json.dumps(summary, ensure_ascii=False, indent=2)}"

    async def read_category_items(self, fc) -> str:
        """Return all items inside a given category."""
        print(f"[ItemAgent] read_category_items called with fc: {fc}")

        category_name = self._clean(fc.args["category_name"])
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

    async def add_category(self, fc) -> str:

        print(f"[ItemAgent] add_category called with fc: {fc}")

        category_name = self._clean(fc.args["category_name"])
        description = fc.args["description"]

        if not category_name:
            return "Category name cannot be empty."

        """
        Add a new category.
        """
        async with self._lock:
            data = await self._load()

            if self._find_key_ci(data, category_name) is not None:
                print(f"[ItemAgent] Category '{category_name}' already exists.")
                return f"Category '{category_name}' already exists."

            data[category_name] = {
                "description": description,
                "items": {}
            }

            if await self._save(data):
                return f"Category '{category_name}' added successfully."
            return f"Error adding category '{category_name}': failed to save data to disk."

    async def item_exists(self, fc) -> bool:

        print(f"[ItemAgent] item_exists called with fc: {fc}")

        """Return True if the item exists inside the given category."""
        data = await self._load()

        category_name = self._clean(fc.args["category_name"])
        item_name = self._clean(fc.args["item_name"])

        real_category = self._find_key_ci(data, category_name)
        if real_category is None:
            return False

        items = data[real_category].get("items", {})
        return self._find_key_ci(items, item_name) is not None

    async def add_item(self, fc) -> str:

        print(f"[ItemAgent] add_item called with fc: {fc}")

        """
        Add a new item to a category.
        """
        category_name = self._clean(fc.args["category_name"])
        item_name = self._clean(fc.args["item_name"])
        value = fc.args["value"]

        if not category_name or not item_name:
            return "Category name and item name cannot be empty."

        async with self._lock:
            data = await self._load()

            real_category = self._find_key_ci(data, category_name)
            if real_category is None:
                print(f"[ItemAgent] Category '{category_name}' not found.")
                return f"Category '{category_name}' not found."

            items = data[real_category].setdefault("items", {})

            if self._find_key_ci(items, item_name) is not None:
                print(f"[ItemAgent] Item '{item_name}' already exists in '{real_category}'.")
                return f"Item '{item_name}' already exists in '{real_category}'."

            items[item_name] = {"value": value}

            if await self._save(data):
                return f"Item '{item_name}' added to category '{real_category}' successfully."
            return f"Error adding item '{item_name}' to category '{real_category}': failed to save data to disk."

    async def search_item(self, fc) -> str:
        """
        Search across all categories for items whose name or value
        contains the query string (case-insensitive).
        """
        print(f"[ItemAgent] search_item called with fc: {fc}")

        query = fc.args["query"]
        data = await self._load()
        query_lower = query.lower()
        results = []

        for category_name, category_data in data.items():
            items = category_data.get("items", {})
            for item_name, item_data in items.items():
                value = str(item_data.get("value", ""))
                if query_lower in item_name.lower() or query_lower in value.lower():
                    results.append({
                        "category": category_name,
                        "item_name": item_name,
                        "value": value
                    })

        if not results:
            return f"No items found matching '{query}'."
        return f"Search results for '{query}': {json.dumps(results, ensure_ascii=False, indent=2)}"

    async def update_item(self, fc) -> str:

        print(f"[ItemAgent] update_item called with fc: {fc}")

        category_name = self._clean(fc.args["category_name"])
        item_name = self._clean(fc.args["item_name"])
        new_value = fc.args["new_value"]

        """
        Update the value of an existing item.
        """
        async with self._lock:
            data = await self._load()

            real_category = self._find_key_ci(data, category_name)
            if real_category is None:
                print(f"[ItemAgent] Category '{category_name}' not found.")
                return f"Category '{category_name}' not found."

            items = data[real_category].get("items", {})
            real_item = self._find_key_ci(items, item_name)

            if real_item is None:
                print(f"[ItemAgent] Item '{item_name}' not found in '{real_category}'.")
                return f"Item '{item_name}' not found in '{real_category}'."

            items[real_item]["value"] = new_value

            if await self._save(data):
                return f"Item '{real_item}' updated in category '{real_category}' successfully."
            return f"Error updating item '{real_item}' in category '{real_category}': failed to save data to disk."

    async def remove_item(self, fc) -> str:

        print(f"[ItemAgent] remove_item called with fc: {fc}")

        """
        Remove an item from a category.
        """
        category_name = self._clean(fc.args["category_name"])
        item_name = self._clean(fc.args["item_name"])

        async with self._lock:
            data = await self._load()

            real_category = self._find_key_ci(data, category_name)
            if real_category is None:
                print(f"[ItemAgent] Category '{category_name}' not found.")
                return f"Category '{category_name}' not found."

            items = data[real_category].get("items", {})
            real_item = self._find_key_ci(items, item_name)

            if real_item is None:
                print(f"[ItemAgent] Item '{item_name}' not found in '{real_category}'.")
                return f"Item '{item_name}' not found in '{real_category}'."

            del items[real_item]

            if await self._save(data):
                return f"Item '{real_item}' removed from category '{real_category}' successfully."
            return f"Error removing item '{real_item}' from category '{real_category}': failed to save data to disk."

    async def handle_function_call(self, fc):
        """Handle a function call from the agent."""

        print(f"[ItemAgent] Handling function call: {fc.name} with args: {fc.args}")

        func_map = {
            "read_categories": self.read_categories,
            "read_category_items": self.read_category_items,
            "add_category": self.add_category,
            "item_exists": self.item_exists,
            "add_item": self.add_item,
            "search_item": self.search_item,
            "update_item": self.update_item,
            "remove_item": self.remove_item
        }

        func = func_map.get(fc.name)
        if not func:
            print(f"[ItemAgent] Unknown function call: {fc.name}")
            return None

        # Extract arguments and call the function
        return await func(fc)


# ─────────────────────────────────────────────────
# Quick smoke-test  (python item_manager_agent.py)
# ─────────────────────────────────────────────────

class _FC:
    """Tiny stand-in for the google-genai function-call object (has .name/.args)."""
    def __init__(self, name, **args):
        self.name = name
        self.args = args


async def _demo():
    items_file_path = "backend/items.json"
    agent = ItemAgent(items_file_path)

    print(await agent.read_categories())

    print("\n── add_category ─────────────────────────────")
    print(await agent.add_category(_FC("add_category", category_name="test_cat", description="a test category")))

    print("\n── add_item ─────────────────────────────────")
    print(await agent.add_item(_FC("add_item", category_name="test_cat", item_name="sam", value="sam@example.com")))

    print("\n── item_exists (different case) ─────────────")
    print(await agent.item_exists(_FC("item_exists", category_name="Test_Cat", item_name="SAM")))   # True
    print(await agent.item_exists(_FC("item_exists", category_name="test_cat", item_name="ghost")))  # False

    print("\n── search_item ('sam') ──────────────────────")
    print(await agent.search_item(_FC("search_item", query="sam")))

    print("\n── update_item ──────────────────────────────")
    print(await agent.update_item(_FC("update_item", category_name="test_cat", item_name="SAM", new_value="samuel@newdomain.com")))

    print("\n── search_item after update ('samuel') ──────")
    print(await agent.search_item(_FC("search_item", query="samuel")))

    print("\n── remove_item ──────────────────────────────")
    print(await agent.remove_item(_FC("remove_item", category_name="test_cat", item_name="sam")))

    print("\n── final categories ─────────────────────────")
    print(await agent.read_categories())


if __name__ == "__main__":
    asyncio.run(_demo())