# Memory plugin

Two halves - use the right one for the data:

## Structured store (contacts, addresses, credentials, and similar discrete facts)
Tools: `read_categories`, `read_category_items`, `add_category`, `add_item`, `item_exists`,
`search_item`, `update_item`, `remove_item`.

- Read the category list when the correct category is unknown; prefer matching by category
  *description* (semantic meaning) over category name.
- If exactly one category clearly fits, use it. If several look relevant, inspect their items and
  choose based on the specific data type.
- Only create a new category when no existing one is suitable; new categories need a specific,
  searchable description.
- Before adding an item, check `item_exists`/`search_item` first - search semantically, since the
  user's wording may differ from the stored item name (e.g. "my dad's email" might already be
  stored as `Dad`, `dad_email`, or `Father`). If it's the same real-world thing, update it rather
  than creating a duplicate.
- If a direct lookup fails, do a semantic search before concluding the information doesn't exist.
- Within one conversation, reuse a category/item you've already read instead of re-fetching it,
  unless you just modified it.
- There is a category named `about_sir` for durable, stable info about the user (interests,
  preferences, personality, communication style). Store a genuinely useful, stable fact there when
  you learn it - don't save every casual statement or anything temporary.

## Notes (USER.md / AGENT.md and similar, unstructured persona memory)
Tools: `write_note`, `append_note`, `read_note`, `list_notes`.

- Use these for durable narrative facts/preferences/persona notes (e.g. "user prefers dark mode",
  "always write comments in English") - not for the kind of discrete fact the structured store
  handles.
- `USER.md` and `AGENT.md` are loaded into context automatically at the start of every session (via
  a system notification), so you don't need to `read_note` them just to "check" - only read a note
  on demand for something beyond what was already injected, or before appending to make sure the
  append still makes sense.
- Each note file has a byte cap; if a write/append is rejected for being over the cap, summarise or
  trim the file first rather than retrying the same write.

## General rule
Never claim to remember something from an earlier conversation unless it's actually available
through the current conversation or these memory tools. Use memory tools when a task needs the
stored info, the user asks about previously stored info, or new information is clearly useful for
future interactions - not for every trivial request.
