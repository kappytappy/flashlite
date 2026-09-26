# FlashLite

A tiny, lightweight flashcard app — no account, no cloud, no bloat. Inspired by
[Flashbang](https://github.com/taylor-hartman/Flashbang)'s minimalism.

Download `FlashLite.exe` from the [Releases page](../../releases), double-click it,
and study. Your decks are saved in `flashlite_data.json` next to the exe, so it's
fully portable — copy the exe + json anywhere.

## Features

- **Decks** — create, rename, delete; cards are front/back pairs
- **Review mode** — classic flip-through with keyboard shortcuts (Space = flip, ←/→ = move)
- **Typing mode** — see the front, type the back, get scored
- **Test mode** — multiple choice with 4 options, scored at the end
- **🔊 Read aloud** — speech synthesis reads the current card (Windows)
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
