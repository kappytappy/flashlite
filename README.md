# FlashLite

A tiny, lightweight flashcard app — no account, no cloud, no bloat. Flashbang-style
UI: monospace everything, keyboard-driven studying, and 10 switchable themes.

Download `FlashLite.exe` from the [Releases page](../../releases), double-click it,
and study. Your decks are saved in `flashlite_data.json` next to the exe, so it's
fully portable — copy the exe + json anywhere.

## Features

- **Decks** — create, rename, delete; cards are front/back pairs
- **Flashcard mode** — Flashbang-style: prompt, Space to reveal, `1` = wrong
  (card comes back later), `2` = right. "N remaining" counts down
- **Typed mode** — see the front, type the back, get scored
- **Test mode** — multiple choice with 4 options, scored at the end
- **10 themes** — Light, Dark, Lemon Mint, Lab, Beehive, Houseplant, Cafe,
  Terminal, Dream, Construction (same palette as Flashbang). Pick in ⚙ settings
- **Study options** — choose your modes, direction (standard / reversed / both),
  and speech (say prompt, say answer)
- **🔊 Read aloud** — speech synthesis (Windows)
- **Import .txt** — one card per line, `front | back` (separator is your choice:
  tab, `|`, `;`, `,`, or anything custom). Preview before importing, into a new
  deck or an existing one
- **Export .txt** — back up any deck to a text file

### .txt format example

```
Capital of France? | Paris
2 + 2 = ? | 4
Largest planet? | Jupiter
```

Lines without the separator (or with an empty front/back) are skipped and counted
in the preview.

## Run from source

```bash
pip install -r requirements.txt
python app.py
```

## License

MIT — see [LICENSE](LICENSE).
