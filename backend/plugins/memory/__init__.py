from pathlib import Path

from plugins.base import tool, lazy_singleton
from .item_store import ItemStore
from .notes import NoteStore

_BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/

get_item_store = lazy_singleton(lambda: ItemStore(str(_BASE_DIR / "structured_data.json")))
get_note_store = lazy_singleton(lambda: NoteStore(str(_BASE_DIR / "memory_notes")))


# ═══════════════════════════════════════════════════════════════
# Structured items: contacts, addresses, folders, emails, credentials, ...
# Same tool names/behavior as the old plugins/items plugin, so this is a
# drop-in replacement - the model doesn't need new instructions for these.
# ═══════════════════════════════════════════════════════════════

@tool(
    name="read_categories",
    description="Lists all available structured-data categories (e.g. contacts, places).",
    parameters={"type": "OBJECT", "properties": {}},
)
async def read_categories(ctx, fc):
    return await get_item_store().read_categories()


@tool(
    name="read_category_items",
    description="Returns all items stored inside a specific category.",
    parameters={
        "type": "OBJECT",
        "properties": {"category_name": {"type": "STRING", "description": "The name of the category to read."}},
        "required": ["category_name"],
    },
)
async def read_category_items(ctx, fc):
    return await get_item_store().read_category_items(fc.args["category_name"])


@tool(
    name="add_category",
    description="Creates a new category for organizing structured items.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "category_name": {"type": "STRING", "description": "The name of the new category."},
            "description": {"type": "STRING", "description": "A description of what this category contains."},
        },
        "required": ["category_name", "description"],
    },
)
async def add_category(ctx, fc):
    return await get_item_store().add_category(fc.args["category_name"], fc.args["description"])


@tool(
    name="add_item",
    description=(
        "Adds a structured, named, addressable piece of data - a phone number, address, "
        "folder path, email, credential - under a category. Use this rather than a note "
        "whenever the data has a clear name and a single value someone might look up later."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "category_name": {"type": "STRING", "description": "The category to add the item to."},
            "item_name": {"type": "STRING", "description": "The name of the item."},
            "value": {"type": "STRING", "description": "The value or content of the item."},
        },
        "required": ["category_name", "item_name", "value"],
    },
)
async def add_item(ctx, fc):
    return await get_item_store().add_item(fc.args["category_name"], fc.args["item_name"], fc.args["value"])


@tool(
    name="item_exists",
    description="Checks if an item exists in a category.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "category_name": {"type": "STRING", "description": "The category name to check in."},
            "item_name": {"type": "STRING", "description": "The item name to search for."},
        },
        "required": ["category_name", "item_name"],
    },
)
async def item_exists(ctx, fc):
    exists = await get_item_store().item_exists(fc.args["category_name"], fc.args["item_name"])
    return "Yes, it exists." if exists else "No, it does not exist."


@tool(
    name="search_item",
    description="Searches structured items across all categories by name or value (contacts, addresses, folders, etc).",
    parameters={
        "type": "OBJECT",
        "properties": {"query": {"type": "STRING", "description": "The search query string."}},
        "required": ["query"],
    },
)
async def search_item(ctx, fc):
    return await get_item_store().search_item(fc.args["query"])


@tool(
    name="update_item",
    description="Updates the value of an existing structured item.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "category_name": {"type": "STRING", "description": "The category containing the item."},
            "item_name": {"type": "STRING", "description": "The name of the item to update."},
            "new_value": {"type": "STRING", "description": "The new value for the item."},
        },
        "required": ["category_name", "item_name", "new_value"],
    },
)
async def update_item(ctx, fc):
    return await get_item_store().update_item(fc.args["category_name"], fc.args["item_name"], fc.args["new_value"])


@tool(
    name="remove_item",
    description="Removes a structured item from a category.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "category_name": {"type": "STRING", "description": "The category containing the item."},
            "item_name": {"type": "STRING", "description": "The name of the item to remove."},
        },
        "required": ["category_name", "item_name"],
    },
    requires_confirmation=True,
)
async def remove_item(ctx, fc):
    return await get_item_store().remove_item(fc.args["category_name"], fc.args["item_name"])


# ═══════════════════════════════════════════════════════════════
# Notes: small .md files folded into the system prompt (USER.md, AGENT.md,
# or any other name the model picks). NOT for structured/high-volume data -
# see add_item above for that.
# ═══════════════════════════════════════════════════════════════

@tool(
    name="write_note",
    description=(
        "Overwrites a persistent .md note (e.g. USER.md, AGENT.md) that gets loaded into "
        "every future session's context. Use for durable, narrative facts/preferences/persona "
        "notes worth Scarlett always knowing - not for structured lookup data (use add_item) "
        "and not for anything that only matters this turn."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING", "description": "Note filename, e.g. 'USER.md' or 'AGENT.md'."},
            "content": {"type": "STRING", "description": "Full replacement content for the note, in markdown."},
        },
        "required": ["name", "content"],
    },
)
async def write_note(ctx, fc):
    return get_note_store().write(fc.args["name"], fc.args["content"])


@tool(
    name="append_note",
    description="Appends one line/fact to an existing .md note without rewriting the whole thing.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING", "description": "Note filename, e.g. 'USER.md'."},
            "line": {"type": "STRING", "description": "The line to append."},
        },
        "required": ["name", "line"],
    },
)
async def append_note(ctx, fc):
    return get_note_store().append(fc.args["name"], fc.args["line"])


@tool(
    name="read_note",
    description="Reads the full current content of a .md note.",
    parameters={
        "type": "OBJECT",
        "properties": {"name": {"type": "STRING", "description": "Note filename, e.g. 'USER.md'."}},
        "required": ["name"],
    },
)
async def read_note(ctx, fc):
    return get_note_store().read(fc.args["name"])


@tool(
    name="list_notes",
    description="Lists all existing .md notes by filename.",
    parameters={"type": "OBJECT", "properties": {}},
)
async def list_notes(ctx, fc):
    names = get_note_store().list_notes()
    return f"Notes: {', '.join(names)}" if names else "No notes yet."
