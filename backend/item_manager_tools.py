# Tool declarations for ItemAgent
# Add these to your Scarlett.py tools list

read_categories_tool = {
    "name": "read_categories",
    "description": "Lists all available item categories.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    }
}

read_category_items_tool = {
    "name": "read_category_items",
    "description": "Returns all items stored inside a specific category.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "category_name": {"type": "STRING", "description": "The name of the category to read."}
        },
        "required": ["category_name"]
    }
}

add_category_tool = {
    "name": "add_category",
    "description": "Creates a new category for organizing items.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "category_name": {"type": "STRING", "description": "The name of the new category."},
            "description": {"type": "STRING", "description": "A description of what this category contains."}
        },
        "required": ["category_name", "description"]
    }
}

add_item_tool = {
    "name": "add_item",
    "description": "Adds a new item to a category.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "category_name": {"type": "STRING", "description": "The category to add the item to."},
            "item_name": {"type": "STRING", "description": "The name of the item."},
            "value": {"type": "STRING", "description": "The value or content of the item."}
        },
        "required": ["category_name", "item_name", "value"]
    }
}

item_exists_tool = {
    "name": "item_exists",
    "description": "Checks if an item exists in a category.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "category_name": {"type": "STRING", "description": "The category name to check in."},
            "item_name": {"type": "STRING", "description": "The item name to search for."}
        },
        "required": ["category_name", "item_name"]
    }
}

search_item_tool = {
    "name": "search_item",
    "description": "Searches for items across all categories by name or value.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {"type": "STRING", "description": "The search query string."}
        },
        "required": ["query"]
    }
}

update_item_tool = {
    "name": "update_item",
    "description": "Updates the value of an existing item in a category.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "category_name": {"type": "STRING", "description": "The category containing the item."},
            "item_name": {"type": "STRING", "description": "The name of the item to update."},
            "new_value": {"type": "STRING", "description": "The new value for the item."}
        },
        "required": ["category_name", "item_name", "new_value"]
    }
}

remove_item_tool = {
    "name": "remove_item",
    "description": "Removes an item from a category.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "category_name": {"type": "STRING", "description": "The category containing the item."},
            "item_name": {"type": "STRING", "description": "The name of the item to remove."}
        },
        "required": ["category_name", "item_name"]
    }
}

# Export all tools
item_manager_tools_list = [{"function_declarations": [
    read_categories_tool,
    read_category_items_tool,
    add_category_tool,
    add_item_tool,
    item_exists_tool,
    search_item_tool,
    update_item_tool,
    remove_item_tool
]}]
