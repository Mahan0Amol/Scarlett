import json
import asyncio
from pathlib import Path


class ItemAgent:
    def __init__(self, items_file_path: str = "backend/items.json"):
        self.items_file_path = items_file_path

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
        """Write data back to disk. Returns True on success."""
        try:
            with open(self.items_file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"[ItemAgent] Failed to save file: {e}")
            return False

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
        
        return f"The list of categories is: {list(data.keys())}"

    async def add_category(self, fc) -> str:

        print(f"[ItemAgent] add_category called with fc: {fc}")

        category_name = fc.args["category_name"]
        description = fc.args["description"]

        """
        Add a new category.
        Returns False (without changes) if the category already exists.
        """
        data = await self._load()

        if category_name in data:
            print(f"[ItemAgent] Category '{category_name}' already exists.")
            return f"Category '{category_name}' already exists."

        data[category_name] = {
            "description": description,
            "items": {}
        }
        try:
            await self._save(data)
            return f"Category '{category_name}' added successfully."
        except Exception as e:
            print(f"[ItemAgent] Error saving data: {e}")
            return f"Error adding category '{category_name}' with error: {e}"
        

    async def item_exists(self, fc) -> bool:

        print(f"[ItemAgent] item_exists called with fc: {fc}")

        """Return True if the item exists inside the given category."""
        data = await self._load()

        category_name = fc.args["category_name"]
        item_name = fc.args["item_name"]

        if category_name not in data:
            return False

        return True if item_name in data[category_name].get("items", {}) else False

    async def add_item(self, fc) -> str:

        print(f"[ItemAgent] add_item called with fc: {fc}")

        """
        Add a new item to a category.
        Returns False if the category doesn't exist or the item already exists.
        """
        data = await self._load()

        category_name = fc.args["category_name"]
        item_name = fc.args["item_name"]
        value = fc.args["value"]

        if category_name not in data:
            print(f"[ItemAgent] Category '{category_name}' not found.")
            return f"Category '{category_name}' not found."

        items = data[category_name].setdefault("items", {})

        if item_name in items:
            print(f"[ItemAgent] Item '{item_name}' already exists in '{category_name}'.")
            return f"Item '{item_name}' already exists in '{category_name}'."

        items[item_name] = {"value": value}
        try:
            await self._save(data)
            return f"Item '{item_name}' added to category '{category_name}' successfully."
        except Exception as e:
            print(f"[ItemAgent] Error saving data: {e}")
            return f"Error adding item '{item_name}' to category '{category_name}' with error: {e}"

    async def search_item(self, fc) -> str:
        """
        Search across all categories for items whose name or value
        contains the query string (case-insensitive).

        Returns a list of matches in the form:
            [
                {
                    "category": "emails",
                    "item_name": "Sam",
                    "value": "sam@example.com"
                },
                ...
            ]
        """
        print(f"[ItemAgent] search_item called with fc: {fc}")

        query = fc.args["query"]
        data = await self._load()
        query_lower = query.lower()
        results = []

        for category_name, category_data in data.items():
            items = category_data.get("items", {})
            for item_name, item_data in items.items():
                value = item_data.get("value", "")
                if query_lower in item_name.lower() or query_lower in value.lower():
                    results.append({
                        "category": category_name,
                        "item_name": item_name,
                        "value": value
                    })

        return f"Search results for '{query}': {results}" if results else f"No items found matching '{query}'."

    async def update_item(self, fc) -> str:

        print(f"[ItemAgent] update_item called with fc: {fc}")

        category_name = fc.args["category_name"]
        item_name = fc.args["item_name"]
        new_value = fc.args["new_value"]

        """
        Update the value of an existing item.
        Returns False if the category or item doesn't exist.
        """
        data = await self._load()

        if category_name not in data:
            print(f"[ItemAgent] Category '{category_name}' not found.")
            return f"Category '{category_name}' not found."

        items = data[category_name].get("items", {})

        if item_name not in items:
            print(f"[ItemAgent] Item '{item_name}' not found in '{category_name}'.")
            return f"Item '{item_name}' not found in '{category_name}'."

        items[item_name]["value"] = new_value
        await self._save(data)
        return f"Item '{item_name}' updated in category '{category_name}' successfully."

    async def remove_item(self, fc) -> str:

        print(f"[ItemAgent] remove_item called with fc: {fc}")

        """
        Remove an item from a category.
        Returns False if the category or item doesn't exist.
        """
        data = await self._load()

        category_name = fc.args["category_name"]
        item_name = fc.args["item_name"]

        if category_name not in data:
            print(f"[ItemAgent] Category '{category_name}' not found.")
            return f"Category '{category_name}' not found."

        items = data[category_name].get("items", {})

        if item_name not in items:
            print(f"[ItemAgent] Item '{item_name}' not found in '{category_name}'.")
            return f"Item '{item_name}' not found in '{category_name}'."

        del items[item_name]
        await self._save(data)
        return f"Item '{item_name}' removed from category '{category_name}' successfully."
    
    async def handle_function_call(self, fc):
        """Handle a function call from the agent."""

        print(f"[ItemAgent] Handling function call: {fc.name} with args: {fc.args}")

        func_map = {
            "read_categories": self.read_categories,
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
# Quick smoke-test  (python item_agent.py)
# ─────────────────────────────────────────────────

async def _demo():
    items_file_path = "backend/items.json"
    agent = ItemAgent(items_file_path)

    # print(await agent.read_categories())

    # print("\n── add_category ─────────────────────────────")
    # print(await agent.add_category("ds", "email adresses"))

    # print("\n── add_item ─────────────────────────────────")
    # print(await agent.add_item("test", "sam", "sam@example.com"))

    # print("\n── item_exists ──────────────────────────────")
    # print(await agent.item_exists("emails", "Sam"))      # True
    # print(await agent.item_exists("emails", "Ghost"))    # False

    # print("\n── search_item ('sam') ──────────────────────")
    # print(await agent.search_item("sam"))

    # print("\n── update_item ──────────────────────────────")
    # print(await agent.update_item("emails", "sam", "samuel@newdomain.com"))   

    # print("\n── search_item after update ('samuel') ──────")
    # print(await agent.search_item("samuel"))

    # print("\n── remove_item ──────────────────────────────")
    # print(await agent.remove_item("phone_numbers", "Dad"))

    # print("\n── final categories ─────────────────────────")
    print(await agent.read_categories(fc=None))


if __name__ == "__main__":
    asyncio.run(_demo())