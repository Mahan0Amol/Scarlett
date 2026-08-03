"""
Item-manager tools. ItemAgent already has a generic handle_function_call(fc)
dispatcher of its own, so each of these plugin handlers is a thin pass-through
that just declares the schema and forwards the raw call to it.
"""

from plugins.base import tool
from .plugin import ItemAgent


def _get_agent(ctx):
    if "item_agent" not in ctx.state:
        ctx.state["item_agent"] = ItemAgent()
    return ctx.state["item_agent"]


async def _delegate(ctx, fc):
    print(f"[TOOL] ItemAgent call: '{fc.name}' args={fc.args}")
    return await _get_agent(ctx).handle_function_call(fc)


@tool(
    name="read_categories",
    description="Lists all available item categories.",
    parameters={"type": "OBJECT", "properties": {}},
)
async def read_categories(ctx, fc):
    return await _delegate(ctx, fc)


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
    return await _delegate(ctx, fc)


@tool(
    name="add_category",
    description="Creates a new category for organizing items.",
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
    return await _delegate(ctx, fc)


@tool(
    name="add_item",
    description="Adds a new item to a category.",
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
    return await _delegate(ctx, fc)


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
    return await _delegate(ctx, fc)


@tool(
    name="search_item",
    description="Searches for items across all categories by name or value.",
    parameters={
        "type": "OBJECT",
        "properties": {"query": {"type": "STRING", "description": "The search query string."}},
        "required": ["query"],
    },
)
async def search_item(ctx, fc):
    return await _delegate(ctx, fc)


@tool(
    name="update_item",
    description="Updates the value of an existing item in a category.",
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
    return await _delegate(ctx, fc)


@tool(
    name="remove_item",
    description="Removes an item from a category.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "category_name": {"type": "STRING", "description": "The category containing the item."},
            "item_name": {"type": "STRING", "description": "The name of the item to remove."},
        },
        "required": ["category_name", "item_name"],
    },
)
async def remove_item(ctx, fc):
    return await _delegate(ctx, fc)
