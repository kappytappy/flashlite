"""FlashLite - pure logic: deck storage and .txt import parsing.

Kept GUI-free so it can be unit-tested headlessly. The GUI lives in app.py.
"""
import json
import os
import sys

APP_NAME = "FlashLite"
DATA_FILENAME = "flashlite_data.json"

# Separator presets offered by the import dialog: key -> actual character.
SEPARATORS = {
    "tab": "\t",
    "pipe": "|",
    "semicolon": ";",
    "comma": ",",
}


def data_path():
    """JSON file lives next to the exe (or next to this file when run as script)."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, DATA_FILENAME)


def load():
    """Return {'decks': [{'name': str, 'cards': [{'front','back'}]}]}."""
    path = data_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("decks"), list):
                # Normalize shape so the GUI never trips on old/odd files.
                for deck in data["decks"]:
                    deck.setdefault("name", "Untitled")
                    deck.setdefault("cards", [])
                    deck["cards"] = [
                        {"front": str(c.get("front", "")), "back": str(c.get("back", ""))}
                        for c in deck["cards"]
                        if isinstance(c, dict)
                    ]
                return normalize(data)
        except Exception:
            pass
    return normalize({"decks": []})


def save(data):
    with open(data_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


DEFAULT_SETTINGS = {
    "theme": "light",
    "modes": {"flashcard": True, "typed": False, "test": False},
    "direction": "standard",  # standard | reversed | both
    "say_prompt": False,
    "say_answer": False,
}


def normalize(data):
    """Fill in missing settings so old data files keep working."""
    data.setdefault("settings", {})
    for key, value in DEFAULT_SETTINGS.items():
        data["settings"].setdefault(key, value)
    for key, value in DEFAULT_SETTINGS["modes"].items():
        data["settings"]["modes"].setdefault(key, value)
    if data["settings"].get("theme") not in THEME_IDS:
        data["settings"]["theme"] = "light"
    return data


# Theme ids in picker order (colors mirror Flashbang's own themes).
THEME_IDS = ["light", "dark", "lemon-mint", "lab", "beehive",
             "houseplant", "cafe", "terminal", "dream", "construction"]


def parse_txt(text, sep):
    """Parse .txt content into cards.

    One card per line: <front><sep><back>. Returns (cards, skipped_count).
    Lines without the separator, blank lines, or lines with an empty
    front/back are skipped and counted.
    """
    cards = []
    skipped = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if sep not in line:
            skipped += 1
            continue
        front, back = line.split(sep, 1)
        front, back = front.strip(), back.strip()
        if not front or not back:
            skipped += 1
            continue
        cards.append({"front": front, "back": back})
    return cards, skipped


def deck_to_txt(deck, sep):
    """Serialize a deck back to .txt lines (for export)."""
    lines = []
    for card in deck["cards"]:
        front = card["front"].replace("\n", " ").strip()
        back = card["back"].replace("\n", " ").strip()
        lines.append(f"{front}{sep}{back}")
    return "\n".join(lines) + ("\n" if lines else "")
