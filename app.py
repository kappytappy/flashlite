"""FlashLite - a tiny, lightweight flashcard app with Flashbang-style UI.

Single exe, no account, no cloud. Monospace everything, 10 switchable themes,
keyboard-driven study flow. Inspired by https://github.com/taylor-hartman/Flashbang
(theme colors mirror Flashbang's own).
"""
import random
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

import flashcards as fc

try:
    from version import VERSION  # stamped at build time by the release workflow
except Exception:
    VERSION = "dev"

REPO_URL = "https://github.com/kappytappy/flashlite"
RELEASES_URL = REPO_URL + "/releases"
FONT = "Courier New"

# User-adjustable text scaling. _FONT_SCALE["v"] is set from saved settings at
# startup; fs(n) converts every hardcoded point size in the app.
_FONT_SCALE = {"v": 1.0}


def fs(n):
    """Scaled font size honoring the user's text-size setting."""
    return max(8, int(round(n * _FONT_SCALE["v"])))


FONT_SIZE_CHOICES = (("Small", 0.85), ("Medium", 1.0), ("Large", 1.15),
                     ("XL", 1.3), ("XXL", 1.6), ("Huge", 2.0))


def wl(n):
    """Wrap length honoring the user's text-size setting, so big text
    doesn't wrap into a narrow column."""
    return max(120, int(round(n * _FONT_SCALE["v"])))

# Theme colors mirror Flashbang's scss variables.
THEMES = {
    "light":        {"name": "Light",        "bg": "#e7e6e1", "fg": "#393e41",
                     "accent": "#393e41", "card": "#f5f4f0", "muted": "#9a9d9f"},
    "dark":         {"name": "Dark",         "bg": "#222831", "fg": "#cccccc",
                     "accent": "#cccccc", "card": "#2c3440", "muted": "#7a828c"},
    "lemon-mint":   {"name": "Lemon Mint",   "bg": "#fffdde", "fg": "#548cff",
                     "accent": "#548cff", "card": "#fffef2", "muted": "#9db4f0"},
    "lab":          {"name": "Lab",          "bg": "#e4e7e6", "fg": "#a583ea",
                     "accent": "#a583ea", "card": "#f0f3f2", "muted": "#bfaee0"},
    "beehive":      {"name": "Beehive",      "bg": "#fcc326", "fg": "#7e370c",
                     "accent": "#7e370c", "card": "#fdd054", "muted": "#a06844"},
    "houseplant":   {"name": "Houseplant",   "bg": "#a7ff83", "fg": "#086972",
                     "accent": "#086972", "card": "#c2ffa0", "muted": "#3d9a8e"},
    "cafe":         {"name": "Cafe",         "bg": "#f4dfba", "fg": "#876445",
                     "accent": "#876445", "card": "#f9e9cb", "muted": "#b08d5f"},
    "terminal":     {"name": "Terminal",     "bg": "#000000", "fg": "#7bf950",
                     "accent": "#7bf950", "card": "#0b120b", "muted": "#2e7d32"},
    "dream":        {"name": "Dream",        "bg": "#091933", "fg": "#0ebcc6",
                     "accent": "#0ebcc6", "card": "#10294d", "muted": "#2a7d8c"},
    "construction": {"name": "Construction", "bg": "#52575d", "fg": "#fddb3a",
                     "accent": "#fddb3a", "card": "#5e646c", "muted": "#a89a4a"},
}


def speak(text):
    """Read text aloud on a background thread; silently no-ops if unavailable."""
    def _run():
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


# --------------------------------------------------------------------------- #
# Dialogs (themed)
# --------------------------------------------------------------------------- #
class CardDialog(simpledialog.Dialog):
    """Add / edit a single card (front + back)."""

    def __init__(self, parent, t, title, front="", back=""):
        self.t = t
        self.front = front
        self.back = back
        super().__init__(parent, title)

    def body(self, master):
        master.configure(bg=self.t["bg"])
        tk.Label(master, text="Front:", font=(FONT, fs(11)),
                 bg=self.t["bg"], fg=self.t["fg"]).grid(row=0, column=0, sticky="w")
        self.front_txt = tk.Text(master, width=46, height=4, wrap="word",
                                 font=(FONT, fs(12)), bg=self.t["card"], fg=self.t["fg"],
                                 insertbackground=self.t["fg"], relief="solid", bd=1)
        self.front_txt.grid(row=1, column=0, padx=5, pady=(0, 8))
        self.front_txt.insert("1.0", self.front)
        tk.Label(master, text="Back:", font=(FONT, fs(11)),
                 bg=self.t["bg"], fg=self.t["fg"]).grid(row=2, column=0, sticky="w")
        self.back_txt = tk.Text(master, width=46, height=4, wrap="word",
                                font=(FONT, fs(12)), bg=self.t["card"], fg=self.t["fg"],
                                insertbackground=self.t["fg"], relief="solid", bd=1)
        self.back_txt.grid(row=3, column=0, padx=5, pady=(0, 5))
        self.back_txt.insert("1.0", self.back)
        return self.front_txt

    def buttonbox(self):
        box = tk.Frame(self, bg=self.t["bg"])
        for text, cmd in (("OK", self.ok), ("Cancel", self.cancel)):
            tk.Button(box, text=text, font=(FONT, fs(11)), width=10,
                      bg=self.t["bg"], fg=self.t["fg"], activebackground=self.t["card"],
                      activeforeground=self.t["fg"], relief="solid", bd=1,
                      command=cmd).pack(side="left", padx=5, pady=5)
        box.pack()
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)

    def apply(self):
        self.front = self.front_txt.get("1.0", "end").strip()
        self.back = self.back_txt.get("1.0", "end").strip()


class ImportDialog(tk.Toplevel):
    """Import cards from a .txt file: pick file, separator, target deck, preview."""

    SEP_CHOICES = [("Tab", "tab"), ("Pipe  |", "pipe"), ("Semicolon  ;", "semicolon"),
                   ("Comma  ,", "comma"), ("Custom", "custom")]

    def __init__(self, parent, t, deck_names):
        super().__init__(parent)
        self.title("Import cards from .txt")
        self.resizable(False, False)
        self.configure(bg=t["bg"])
        self.t = t
        self.result = None
        self._deck_names = deck_names
        self._cards = []

        self.file_var = tk.StringVar()
        self.sep_var = tk.StringVar(value="pipe")
        self.custom_var = tk.StringVar(value=":")
        self.target_var = tk.StringVar(value="new")
        self.newname_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Pick a .txt file to begin.")

        frm = tk.Frame(self, bg=t["bg"])
        frm.pack(padx=14, pady=14)

        def lab(text):
            return tk.Label(frm, text=text, font=(FONT, fs(11)), bg=t["bg"], fg=t["fg"])

        lab("File:").grid(row=0, column=0, sticky="w")
        tk.Entry(frm, textvariable=self.file_var, width=40, font=(FONT, fs(11)),
                 bg=t["card"], fg=t["fg"], insertbackground=t["fg"],
                 relief="solid", bd=1).grid(row=0, column=1, padx=5)
        self._btn(frm, "Browse…", self._browse).grid(row=0, column=2)

        lab("Separator:").grid(row=1, column=0, sticky="w", pady=(10, 0))
        sepfrm = tk.Frame(frm, bg=t["bg"])
        sepfrm.grid(row=1, column=1, columnspan=2, sticky="w", pady=(10, 0))
        for label, key in self.SEP_CHOICES:
            tk.Radiobutton(sepfrm, text=label, value=key, variable=self.sep_var,
                           font=(FONT, fs(10)), bg=t["bg"], fg=t["fg"],
                           selectcolor=t["card"], activebackground=t["bg"],
                           command=self._reparse).pack(side="left", padx=(0, 4))
        tk.Entry(sepfrm, textvariable=self.custom_var, width=4, font=(FONT, fs(10)),
                 bg=t["card"], fg=t["fg"], insertbackground=t["fg"],
                 relief="solid", bd=1).pack(side="left")
        self.custom_var.trace_add("write", lambda *a: self._reparse())

        lab("Add to:").grid(row=2, column=0, sticky="w", pady=(10, 0))
        tgtfrm = tk.Frame(frm, bg=t["bg"])
        tgtfrm.grid(row=2, column=1, columnspan=2, sticky="w", pady=(10, 0))
        tk.Radiobutton(tgtfrm, text="New deck:", value="new", variable=self.target_var,
                       font=(FONT, fs(10)), bg=t["bg"], fg=t["fg"],
                       selectcolor=t["card"], activebackground=t["bg"]).pack(side="left")
        tk.Entry(tgtfrm, textvariable=self.newname_var, width=16, font=(FONT, fs(10)),
                 bg=t["card"], fg=t["fg"], insertbackground=t["fg"],
                 relief="solid", bd=1).pack(side="left", padx=5)
        tk.Radiobutton(tgtfrm, text="Existing:", value="existing",
                       variable=self.target_var, font=(FONT, fs(10)), bg=t["bg"],
                       fg=t["fg"], selectcolor=t["card"],
                       activebackground=t["bg"]).pack(side="left", padx=(6, 0))
        self.existing_list = tk.Listbox(tgtfrm, height=1, width=16, font=(FONT, fs(10)),
                                        bg=t["card"], fg=t["fg"], relief="solid", bd=1,
                                        exportselection=False)
        for name in deck_names:
            self.existing_list.insert("end", name)
        self.existing_list.pack(side="left", padx=5)
        if deck_names:
            self.existing_list.selection_set(0)

        lab("Preview:").grid(row=3, column=0, sticky="nw", pady=(10, 0))
        self.preview = tk.Listbox(frm, width=58, height=8, font=(FONT, fs(10)),
                                  bg=t["card"], fg=t["fg"], relief="solid", bd=1)
        self.preview.grid(row=3, column=1, columnspan=2, pady=(10, 0))
        tk.Label(frm, textvariable=self.status_var, font=(FONT, fs(10)),
                 bg=t["bg"], fg=t["muted"]).grid(row=4, column=1, columnspan=2,
                                                 sticky="w", pady=(4, 0))

        btnfrm = tk.Frame(frm, bg=t["bg"])
        btnfrm.grid(row=5, column=1, columnspan=2, sticky="e", pady=(12, 0))
        self._btn(btnfrm, "Import", self._do_import).pack(side="left", padx=5)
        self._btn(btnfrm, "Cancel", self.destroy).pack(side="left")

        self.transient(parent)
        self.grab_set()

    def _btn(self, parent, text, cmd):
        t = self.t
        return tk.Button(parent, text=text, font=(FONT, fs(11)), command=cmd,
                         bg=t["bg"], fg=t["fg"], activebackground=t["card"],
                         activeforeground=t["fg"], relief="solid", bd=1, padx=10)

    def _sep(self):
        key = self.sep_var.get()
        if key == "custom":
            return self.custom_var.get() or ":"
        return fc.SEPARATORS[key]

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Pick a .txt file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self.file_var.set(path)
            import os
            base = os.path.splitext(os.path.basename(path))[0]
            if not self.newname_var.get():
                self.newname_var.set(base)
            self._reparse()

    def _reparse(self, *args):
        path = self.file_var.get().strip()
        self._cards = []
        self.preview.delete(0, "end")
        if not path:
            self.status_var.set("Pick a .txt file to begin.")
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                text = f.read()
        except Exception as exc:
            self.status_var.set(f"Could not read file: {exc}")
            return
        cards, skipped = fc.parse_txt(text, self._sep())
        self._cards = cards
        for card in cards[:15]:
            self.preview.insert("end", f"{card['front'][:30]}  ->  {card['back'][:30]}")
        if len(cards) > 15:
            self.preview.insert("end", f"... and {len(cards) - 15} more")
        msg = f"{len(cards)} card(s) ready"
        if skipped:
            msg += f", {skipped} line(s) skipped"
        self.status_var.set(msg)

    def _do_import(self):
        if not self._cards:
            messagebox.showwarning("Nothing to import",
                                   "No cards parsed. Check the file and separator.",
                                   parent=self)
            return
        if self.target_var.get() == "new":
            name = self.newname_var.get().strip()
            if not name:
                messagebox.showwarning("Name needed", "Give the new deck a name.",
                                       parent=self)
                return
            target = ("new", name)
        else:
            sel = self.existing_list.curselection()
            if not sel:
                messagebox.showwarning("No deck", "Pick an existing deck.", parent=self)
                return
            target = ("existing", sel[0])
        self.result = (target, self._cards)
        self.destroy()


class ExportDialog(tk.Toplevel):
    """Export the current deck to .txt with a chosen separator."""

    def __init__(self, parent, t, deck):
        super().__init__(parent)
        self.title("Export deck to .txt")
        self.resizable(False, False)
        self.configure(bg=t["bg"])
        self.t = t
        self.deck = deck
        self.sep_var = tk.StringVar(value="pipe")

        frm = tk.Frame(self, bg=t["bg"])
        frm.pack(padx=14, pady=14)
        tk.Label(frm, text="Separator:", font=(FONT, fs(11)),
                 bg=t["bg"], fg=t["fg"]).grid(row=0, column=0, sticky="w")
        sepfrm = tk.Frame(frm, bg=t["bg"])
        sepfrm.grid(row=0, column=1, sticky="w")
        for label, key in [("Tab", "tab"), ("Pipe  |", "pipe"),
                           ("Semicolon  ;", "semicolon"), ("Comma  ,", "comma")]:
            tk.Radiobutton(sepfrm, text=label, value=key, variable=self.sep_var,
                           font=(FONT, fs(10)), bg=t["bg"], fg=t["fg"],
                           selectcolor=t["card"],
                           activebackground=t["bg"]).pack(side="left", padx=(0, 4))
        btnfrm = tk.Frame(frm, bg=t["bg"])
        btnfrm.grid(row=1, column=0, columnspan=2, sticky="e", pady=(12, 0))
        tk.Button(btnfrm, text="Save…", font=(FONT, fs(11)), command=self._save,
                  bg=t["bg"], fg=t["fg"], activebackground=t["card"],
                  activeforeground=t["fg"], relief="solid", bd=1, padx=10).pack(
                      side="left", padx=5)
        tk.Button(btnfrm, text="Cancel", font=(FONT, fs(11)), command=self.destroy,
                  bg=t["bg"], fg=t["fg"], activebackground=t["card"],
                  activeforeground=t["fg"], relief="solid", bd=1, padx=10).pack(
                      side="left")
        self.transient(parent)
        self.grab_set()

    def _save(self):
        path = filedialog.asksaveasfilename(
            title="Save deck as .txt", defaultextension=".txt",
            filetypes=[("Text files", "*.txt")], parent=self)
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(fc.deck_to_txt(self.deck, fc.SEPARATORS[self.sep_var.get()]))
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)
            return
        messagebox.showinfo("Exported", f"Saved {len(self.deck['cards'])} cards.",
                            parent=self)
        self.destroy()


# --------------------------------------------------------------------------- #
# Main app
# --------------------------------------------------------------------------- #
class FlashLite(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"FlashLite {VERSION}")
        self.geometry("760x620")
        self.minsize(600, 500)

        self.data = fc.load()
        if not self.data["decks"]:
            self.data["decks"].append({
                "name": "Example",
                "cards": [
                    {"front": "Capital of France?", "back": "Paris"},
                    {"front": "2 + 2 = ?", "back": "4"},
                    {"front": "Largest planet?", "back": "Jupiter"},
                ],
            })
            fc.save(self.data)

        self.settings = self.data["settings"]
        self.t = THEMES[self.settings["theme"]]
        _FONT_SCALE["v"] = float(self.settings.get("font_scale", 1.0))
        self.deck_idx = None
        self.screen = "home"

        self._build_ui()
        self.show("home")

    # -- theming helpers ---------------------------------------------------- #
    def _build_ui(self):
        self.configure(bg=self.t["bg"])
        for child in list(self.children.values()):
            try:
                child.destroy()
            except Exception:
                pass
        self.screens = {}
        for name, builder in (("home", self._build_home),
                              ("deck", self._build_deck),
                              ("study", self._build_study),
                              ("settings", self._build_settings)):
            frame = tk.Frame(self, bg=self.t["bg"])
            builder(frame)
            self.screens[name] = frame

    def show(self, name):
        self.screen = name
        for n, frame in self.screens.items():
            frame.pack_forget()
        self.screens[name].pack(fill="both", expand=True)
        refresh = getattr(self, f"_refresh_{name}", None)
        if refresh:
            refresh()

    def _restyle(self):
        """Rebuild every screen in the current theme (keeps screen + deck)."""
        cur, idx = self.screen, self.deck_idx
        self.t = THEMES[self.settings["theme"]]
        self._build_ui()
        self.deck_idx = idx
        self.show(cur)

    def _save(self):
        fc.save(self.data)

    # -- tiny widget factories ---------------------------------------------- #
    def L(self, parent, text, size=fs(12), bold=False, fg=None, **kw):
        return tk.Label(parent, text=text, font=(FONT, size, "bold" if bold else "normal"),
                        bg=self.t["bg"], fg=fg or self.t["fg"], **kw)

    def B(self, parent, text, cmd, size=fs(11), bold=False, width=None):
        return tk.Button(parent, text=text, font=(FONT, size, "bold" if bold else "normal"),
                         bg=self.t["bg"], fg=self.t["fg"],
                         activebackground=self.t["card"], activeforeground=self.t["fg"],
                         relief="solid", bd=1, padx=10, pady=4,
                         command=cmd, **({"width": width} if width else {}))

    def topbar(self, parent, left_text=None, left_cmd=None,
               right_text=None, right_cmd=None):
        bar = tk.Frame(parent, bg=self.t["bg"])
        bar.pack(fill="x", padx=10, pady=8)
        if left_text:
            tk.Button(bar, text=left_text, font=(FONT, fs(16)), command=left_cmd,
                      bg=self.t["bg"], fg=self.t["fg"], activebackground=self.t["card"],
                      relief="flat", bd=0, padx=8).pack(side="left")
        else:
            tk.Frame(bar, bg=self.t["bg"], width=40).pack(side="left")
        if right_text:
            tk.Button(bar, text=right_text, font=(FONT, fs(16)), command=right_cmd,
                      bg=self.t["bg"], fg=self.t["fg"], activebackground=self.t["card"],
                      relief="flat", bd=0, padx=8).pack(side="right")
        return bar

    # ======================================================================= #
    # HOME — deck list
    # ======================================================================= #
    def _build_home(self, root):
        self.topbar(root, left_text="⚙", left_cmd=lambda: self.show("settings"),
                    right_text="+", right_cmd=self._new_deck)
        self.L(root, "FlashLite", size=fs(24), bold=True).pack(pady=(6, 2))
        self.L(root, "pick a deck to study", size=fs(11), fg=self.t["muted"]).pack(pady=(0, 10))

        self.home_decks = tk.Frame(root, bg=self.t["bg"])
        self.home_decks.pack(fill="both", expand=True, padx=40)

        bottom = tk.Frame(root, bg=self.t["bg"])
        bottom.pack(pady=14)
        self.B(bottom, "Import .txt …", self._import_txt).pack(side="left", padx=6)
        self.L(root, f"v{VERSION}", size=fs(9), fg=self.t["muted"]).pack(pady=(0, 8))

    def _refresh_home(self):
        for child in self.home_decks.winfo_children():
            child.destroy()
        decks = self.data["decks"]
        if not decks:
            self.L(self.home_decks, "no decks yet — make one with +",
                   size=fs(12), fg=self.t["muted"]).pack(pady=30)
            return
        for i, deck in enumerate(decks):
            row = tk.Frame(self.home_decks, bg=self.t["bg"])
            row.pack(fill="x", pady=3)
            b = tk.Button(row, text=f"{deck['name']}   ({len(deck['cards'])})",
                          font=(FONT, fs(14)), bg=self.t["card"], fg=self.t["fg"],
                          activebackground=self.t["accent"], activeforeground=self.t["bg"],
                          relief="solid", bd=1, padx=12, pady=8, anchor="w",
                          command=lambda i=i: self._open_deck(i))
            b.pack(fill="x")

    def _open_deck(self, i):
        self.deck_idx = i
        self.show("deck")

    # ======================================================================= #
    # DECK — cards in one deck
    # ======================================================================= #
    def _build_deck(self, root):
        self.topbar(root, left_text="‹", left_cmd=lambda: self.show("home"),
                    right_text="⚙", right_cmd=lambda: self.show("settings"))
        self.deck_title = self.L(root, "", size=fs(22), bold=True)
        self.deck_title.pack(pady=(2, 2))
        self.deck_sub = self.L(root, "", size=fs(11), fg=self.t["muted"])
        self.deck_sub.pack(pady=(0, 8))

        self.card_list = tk.Listbox(root, font=(FONT, fs(12)), bg=self.t["card"],
                                    fg=self.t["fg"], selectbackground=self.t["accent"],
                                    selectforeground=self.t["bg"], relief="solid", bd=1,
                                    exportselection=False)
        self.card_list.pack(fill="both", expand=True, padx=40, pady=4)
        self.card_list.bind("<Double-Button-1>", lambda e: self._edit_card_at_cursor())

        self.study_row = tk.Frame(root, bg=self.t["bg"])
        self.study_row.pack(pady=(8, 2))

        ops = tk.Frame(root, bg=self.t["bg"])
        ops.pack(pady=(2, 14))
        self.B(ops, "Add card", self._add_card).pack(side="left", padx=4)
        self.B(ops, "Import .txt …", self._import_txt).pack(side="left", padx=4)
        self.B(ops, "Export .txt …", self._export_txt).pack(side="left", padx=4)
        self.B(ops, "Rename", self._rename_deck).pack(side="left", padx=4)
        self.B(ops, "Delete", self._delete_deck).pack(side="left", padx=4)

    def _refresh_deck(self):
        deck = self.data["decks"][self.deck_idx]
        self.deck_title.config(text=deck["name"])
        n = len(deck["cards"])
        self.deck_sub.config(text=f"{n} card{'s' if n != 1 else ''}")
        self.card_list.delete(0, "end")
        for card in deck["cards"]:
            front = card["front"].replace("\n", " ")
            back = card["back"].replace("\n", " ")
            if len(front) > 30:
                front = front[:30] + "…"
            if len(back) > 30:
                back = back[:30] + "…"
            self.card_list.insert("end", f"{front}  →  {back}")
        for child in self.study_row.winfo_children():
            child.destroy()
        modes = [("flashcard", "📖 Flashcards"), ("typed", "⌨ Typed"), ("test", "✓ Test")]
        any_mode = False
        for key, label in modes:
            if self.settings["modes"].get(key) and n > 0:
                any_mode = True
                self.B(self.study_row, f"Study: {label}",
                       lambda key=key: self._start_study(key)).pack(side="left", padx=4)
        if not any_mode:
            hint = "enable a study mode in ⚙ settings" if n > 0 else "add cards to study"
            self.L(self.study_row, hint, size=fs(11), fg=self.t["muted"]).pack()

    # ======================================================================= #
    # STUDY — Flashbang-style flow
    # ======================================================================= #
    def _build_study(self, root):
        self.topbar(root, left_text="‹", left_cmd=self._quit_study,
                    right_text="⚙", right_cmd=lambda: self.show("settings"))
        self.study_title = self.L(root, "", size=fs(22), bold=True)
        self.study_title.pack(pady=(2, 12))

        mid = tk.Frame(root, bg=self.t["bg"])
        mid.pack(fill="both", expand=True, padx=40)
        # The card block floats in the true middle of the window.
        center = tk.Frame(mid, bg=self.t["bg"])
        center.place(relx=0.5, rely=0.5, anchor="center", relwidth=1.0)

        self.prompt_lbl = tk.Label(center, text="", font=(FONT, fs(18)), wraplength=wl(560),
                                   bg=self.t["bg"], fg=self.t["fg"], justify="center")
        self.prompt_lbl.pack(pady=(10, 10))
        tk.Frame(center, height=2, bg=self.t["fg"]).pack(fill="x", padx=60, pady=4)
        self.answer_lbl = tk.Label(center, text="", font=(FONT, fs(18)), wraplength=wl(560),
                                   bg=self.t["bg"], fg=self.t["fg"], justify="center")
        self.answer_lbl.pack(pady=(10, 4))

        # typed-mode widgets (hidden unless typed mode)
        self.type_entry = tk.Entry(center, font=(FONT, fs(14)), width=34, justify="center",
                                   bg=self.t["card"], fg=self.t["fg"],
                                   insertbackground=self.t["fg"], relief="solid", bd=1)
        self.type_check_btn = self.B(center, "Check", self._typed_check)

        # test-mode widgets (hidden unless test mode)
        self.opt_frame = tk.Frame(center, bg=self.t["bg"])
        self.opt_buttons = []
        for i in range(4):
            b = tk.Button(self.opt_frame, text="", font=(FONT, fs(13)), wraplength=wl(480),
                          bg=self.t["card"], fg=self.t["fg"],
                          activebackground=self.t["accent"], relief="solid", bd=1,
                          padx=10, pady=6, anchor="w",
                          command=lambda i=i: self._test_pick(i))
            b.pack(fill="x", pady=3)
            self.opt_buttons.append(b)

        self.study_feedback = self.L(center, "", size=fs(13), bold=True)
        self.study_feedback.pack(pady=6)

        bot = tk.Frame(root, bg=self.t["bg"])
        bot.pack(pady=(4, 6))
        self.remaining_lbl = self.L(bot, "", size=fs(12))
        self.remaining_lbl.pack()
        self.hint1 = self.L(bot, "", size=fs(11), fg=self.t["muted"])
        self.hint1.pack()
        self.hint2 = self.L(bot, "", size=fs(11), fg=self.t["muted"])
        self.hint2.pack()

        editbar = tk.Frame(root, bg=self.t["bg"])
        editbar.pack(fill="x", padx=12, pady=(0, 10))
        tk.Button(editbar, text="✎", font=(FONT, fs(14)), command=self._edit_current_card,
                  bg=self.t["bg"], fg=self.t["fg"], activebackground=self.t["card"],
                  relief="flat", bd=0).pack(side="left")
        tk.Button(editbar, text="🔊", font=(FONT, fs(14)), command=self._speak_current,
                  bg=self.t["bg"], fg=self.t["fg"], activebackground=self.t["card"],
                  relief="flat", bd=0).pack(side="left", padx=6)

    # -- study state -------------------------------------------------------- #
    def _deck(self):
        return self.data["decks"][self.deck_idx]

    def _start_study(self, mode):
        deck = self._deck()
        if not deck["cards"]:
            return
        self.study_mode = mode
        self.study_title.config(text=deck["name"])
        # build queue of (card, direction): direction True = front->back
        dirs = {"standard": [True], "reversed": [False], "both": [True, False]}[
            self.settings["direction"]]
        self.queue = [(c, d) for c in deck["cards"] for d in dirs]
        random.shuffle(self.queue)
        self.right = 0
        self.wrong = 0
        self.flipped = False
        self._study_next()
        self.show("study")

    def _quit_study(self):
        for seq in ("<space>", "1", "2", "<Return>"):
            try:
                self.unbind(seq)
            except Exception:
                pass
        self.show("deck")

    def _q(self, card, direction):
        return card["front"] if direction else card["back"]

    def _a(self, card, direction):
        return card["back"] if direction else card["front"]

    def _study_next(self):
        if not self.queue:
            self._study_done()
            return
        self.flipped = False
        self.card, self.direction = self.queue[0]
        prompt = self._q(self.card, self.direction)
        self.prompt_lbl.config(text=prompt)
        self.answer_lbl.config(text="")
        self.study_feedback.config(text="")
        self._show_mode_widgets()
        remaining = len(self.queue)
        self.remaining_lbl.config(text=f"{remaining} remaining")
        if self.settings["say_prompt"]:
            speak(prompt)
        if self.study_mode == "flashcard":
            self.hint1.config(text="Incorrect: Press 1")
            self.hint2.config(text="Correct: Press 2 or Space")
            self.bind("<space>", lambda e: self._fc_flip_or_correct())
            self.bind("1", lambda e: self._fc_mark(False))
            self.bind("2", lambda e: self._fc_mark(True))
        elif self.study_mode == "typed":
            self.hint1.config(text="type the answer, then press Enter")
            self.hint2.config(text="")
            self.type_entry.delete(0, "end")
            self.type_entry.focus_set()
            self.bind("<Return>", lambda e: self._typed_check())
        else:  # test
            self.hint1.config(text="pick the matching answer")
            self.hint2.config(text="")
            self._test_build_options()

    def _show_mode_widgets(self):
        is_typed = self.study_mode == "typed"
        is_test = self.study_mode == "test"
        # Reset everything, then pack in a fixed order per mode. This keeps
        # the test options directly under the divider instead of leaving a
        # dead gap from the (empty, unused) answer/feedback labels.
        for w in (self.type_entry, self.type_check_btn, self.opt_frame,
                  self.answer_lbl, self.study_feedback):
            w.pack_forget()
        if self.study_mode == "flashcard":
            self.answer_lbl.pack(pady=(10, 4))
        if is_typed:
            self.type_entry.pack(pady=6)
            self.type_check_btn.pack(pady=2)
        if is_test:
            self.opt_frame.pack(fill="x", pady=6)
        if not is_test:
            self.study_feedback.pack(pady=6)

    def _study_done(self):
        total = self.right + self.wrong
        messagebox.showinfo("Done!",
                            f"Finished “{self._deck()['name']}”\n"
                            f"Correct: {self.right}/{total}",
                            parent=self)
        self._quit_study()

    # -- flashcard mode ------------------------------------------------------ #
    def _fc_flip_or_correct(self):
        if not self.flipped:
            self.flipped = True
            answer = self._a(self.card, self.direction)
            self.answer_lbl.config(text=answer)
            if self.settings["say_answer"]:
                speak(answer)
        else:
            self._fc_mark(True)

    def _fc_mark(self, correct):
        if not self.flipped:
            return  # must reveal the answer first
        self.queue.pop(0)
        if correct:
            self.right += 1
        else:
            self.wrong += 1
            # re-queue a few cards later so it comes back
            self.queue.insert(min(3, len(self.queue)), (self.card, self.direction))
        self._study_next()

    # -- typed mode ---------------------------------------------------------- #
    def _typed_check(self):
        given = self.type_entry.get().strip().lower()
        want = self._a(self.card, self.direction).strip().lower()
        self.queue.pop(0)
        if given and given == want:
            self.right += 1
            self.study_feedback.config(text="✔ correct", fg="#7bf950")
            self.after(600, self._study_next)
        else:
            self.wrong += 1
            self.study_feedback.config(
                text=f"✘  {self._a(self.card, self.direction)}", fg="#ea4848")
            self.queue.append((self.card, self.direction))
            self.after(1400, self._study_next)

    # -- test mode ----------------------------------------------------------- #
    def _test_build_options(self):
        correct = self._a(self.card, self.direction)
        if self.direction:
            pool = [c["back"] for c in self._deck()["cards"] if c["back"] != correct]
        else:
            pool = [c["front"] for c in self._deck()["cards"] if c["front"] != correct]
        random.shuffle(pool)
        options = [correct] + pool[:3]
        random.shuffle(options)
        self._correct = correct
        for btn, opt in zip(self.opt_buttons, options):
            btn.config(text=opt, bg=self.t["card"], fg=self.t["fg"], state="normal")
        for btn in self.opt_buttons[len(options):]:
            btn.config(text="", state="disabled")

    def _test_pick(self, i):
        btn = self.opt_buttons[i]
        if not btn["text"] or btn["state"] == "disabled":
            return
        for b in self.opt_buttons:
            b.config(state="disabled")
        self.queue.pop(0)
        if btn["text"] == self._correct:
            self.right += 1
            btn.config(bg="#b2cc3e", fg="#000000")
            self.after(600, self._study_next)
        else:
            self.wrong += 1
            btn.config(bg="#ea4848", fg="#ffffff")
            for b in self.opt_buttons:
                if b["text"] == self._correct:
                    b.config(bg="#b2cc3e", fg="#000000")
            self.queue.append((self.card, self.direction))
            self.after(1400, self._study_next)

    def _edit_current_card(self):
        if self.screen != "study" or not getattr(self, "queue", None):
            return
        dlg = CardDialog(self, self.t, "Edit card",
                         self.card["front"], self.card["back"])
        if dlg.front and dlg.back:
            self.card["front"], self.card["back"] = dlg.front, dlg.back
            self._save()
            self._study_next()  # re-render with new text

    def _speak_current(self):
        if self.screen != "study" or not getattr(self, "queue", None):
            return
        speak(self._a(self.card, self.direction) if self.flipped
              else self._q(self.card, self.direction))

    # ======================================================================= #
    # SETTINGS — themes + study options
    # ======================================================================= #
    def _build_settings(self, root):
        self.topbar(root, left_text="‹", left_cmd=lambda: self.show("home"))

        canvas = tk.Canvas(root, bg=self.t["bg"], highlightthickness=0)
        scroll = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=self.t["bg"])
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=4)
        scroll.pack(side="right", fill="y")

        # Mouse-wheel scrolling (tkinter doesn't bind this by itself).
        def _wheel(event):
            if event.num == 4:
                canvas.yview_scroll(-3, "units")
            elif event.num == 5:
                canvas.yview_scroll(3, "units")
            else:
                # Windows: delta = ±120 per notch; macOS sends smaller values
                steps = int(event.delta / 120) or (-1 if event.delta < 0 else 1)
                canvas.yview_scroll(-steps * 3, "units")

        def _bind_wheel(event):
            canvas.bind_all("<MouseWheel>", _wheel)   # Windows / macOS
            canvas.bind_all("<Button-4>", _wheel)     # Linux scroll up
            canvas.bind_all("<Button-5>", _wheel)     # Linux scroll down

        def _unbind_wheel(event):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)

        def heading(text):
            f = tk.Frame(inner, bg=self.t["bg"])
            f.pack(fill="x", pady=(12, 6), padx=10)
            self.L(f, text, size=fs(16), bold=True).pack(side="left")
            tk.Frame(f, height=2, bg=self.t["fg"]).pack(side="left", fill="x",
                                                       expand=True, padx=(10, 0))

        heading("Theme")
        tgrid = tk.Frame(inner, bg=self.t["bg"])
        tgrid.pack(padx=10)
        for col, tid in enumerate(fc.THEME_IDS):
            th = THEMES[tid]
            cell = tk.Frame(tgrid, bg=self.t["bg"])
            cell.grid(row=col // 5, column=col % 5, padx=10, pady=6)
            cv = tk.Canvas(cell, width=56, height=56, bg=self.t["bg"],
                           highlightthickness=0)
            cv.pack()
            cv.create_oval(4, 4, 52, 52, fill=th["accent"], outline=th["accent"])
            cv.create_oval(14, 14, 42, 42, fill=th["bg"], outline=th["bg"])
            if tid == self.settings["theme"]:
                cv.create_oval(1, 1, 55, 55, outline=th["fg"], width=3)
            cv.bind("<Button-1>", lambda e, tid=tid: self._pick_theme(tid))
            self.L(cell, th["name"], size=fs(10)).pack()
            cell.bind("<Button-1>", lambda e, tid=tid: self._pick_theme(tid))

        heading("Study")
        s = self.settings
        opts = tk.Frame(inner, bg=self.t["bg"])
        opts.pack(fill="x", padx=10)
        self.mode_vars = {}
        for key, label in (("flashcard", "Flashcard"), ("typed", "Typed"), ("test", "Test")):
            var = tk.BooleanVar(value=s["modes"].get(key, False))
            self.mode_vars[key] = var
            tk.Checkbutton(opts, text=label, variable=var, font=(FONT, fs(12)),
                           bg=self.t["bg"], fg=self.t["fg"], selectcolor=self.t["card"],
                           activebackground=self.t["bg"], activeforeground=self.t["fg"],
                           command=self._save_study_opts).pack(anchor="w", pady=2)
        self.L(opts, "Direction:", size=fs(12), bold=True).pack(anchor="w", pady=(10, 2))
        self.dir_var = tk.StringVar(value=s["direction"])
        for key, label in (("standard", "Standard (front → back)"),
                           ("reversed", "Reversed (back → front)"),
                           ("both", "Both")):
            tk.Radiobutton(opts, text=label, value=key, variable=self.dir_var,
                           font=(FONT, fs(12)), bg=self.t["bg"], fg=self.t["fg"],
                           selectcolor=self.t["card"], activebackground=self.t["bg"],
                           activeforeground=self.t["fg"],
                           command=self._save_study_opts).pack(anchor="w", pady=2)
        self.L(opts, "Text size:", size=fs(12), bold=True).pack(anchor="w", pady=(10, 2))
        self.fontsize_var = tk.StringVar(value=str(s.get("font_scale", 1.0)))
        for label, val in FONT_SIZE_CHOICES:
            tk.Radiobutton(opts, text=label, value=str(val),
                           variable=self.fontsize_var, font=(FONT, fs(12)),
                           bg=self.t["bg"], fg=self.t["fg"],
                           selectcolor=self.t["card"], activebackground=self.t["bg"],
                           activeforeground=self.t["fg"],
                           command=self._apply_fontsize).pack(anchor="w", pady=2)
        self.L(opts, "Speech:", size=fs(12), bold=True).pack(anchor="w", pady=(10, 2))
        self.say_prompt_var = tk.BooleanVar(value=s["say_prompt"])
        self.say_answer_var = tk.BooleanVar(value=s["say_answer"])
        tk.Checkbutton(opts, text="Say Prompt", variable=self.say_prompt_var,
                       font=(FONT, fs(12)), bg=self.t["bg"], fg=self.t["fg"],
                       selectcolor=self.t["card"], activebackground=self.t["bg"],
                       activeforeground=self.t["fg"],
                       command=self._save_study_opts).pack(anchor="w", pady=2)
        tk.Checkbutton(opts, text="Say Answer", variable=self.say_answer_var,
                       font=(FONT, fs(12)), bg=self.t["bg"], fg=self.t["fg"],
                       selectcolor=self.t["card"], activebackground=self.t["bg"],
                       activeforeground=self.t["fg"],
                       command=self._save_study_opts).pack(anchor="w", pady=2)

        heading("About")
        about = tk.Frame(inner, bg=self.t["bg"])
        about.pack(fill="x", padx=10, pady=(0, 20))
        self.L(about, f"FlashLite v{VERSION}", size=fs(11), fg=self.t["muted"]).pack(anchor="w")
        self.B(about, "Check for updates",
               lambda: webbrowser.open(RELEASES_URL)).pack(anchor="w", pady=6)

    def _refresh_settings(self):
        # rebuilt each time the screen is shown, so just rebuild
        self.screens["settings"].destroy()
        frame = tk.Frame(self, bg=self.t["bg"])
        self._build_settings(frame)
        self.screens["settings"] = frame
        if self.screen == "settings":
            frame.pack(fill="both", expand=True)

    def _pick_theme(self, tid):
        self.settings["theme"] = tid
        self._save()
        self._restyle()

    def _apply_fontsize(self):
        self.settings["font_scale"] = float(self.fontsize_var.get())
        _FONT_SCALE["v"] = self.settings["font_scale"]
        self._save()
        self._restyle()

    def _save_study_opts(self):
        for key, var in self.mode_vars.items():
            self.settings["modes"][key] = var.get()
        self.settings["direction"] = self.dir_var.get()
        self.settings["say_prompt"] = self.say_prompt_var.get()
        self.settings["say_answer"] = self.say_answer_var.get()
        self._save()

    # ======================================================================= #
    # Deck / card ops
    # ======================================================================= #
    def _new_deck(self):
        name = simpledialog.askstring("New deck", "Deck name:", parent=self)
        if name and name.strip():
            self.data["decks"].append({"name": name.strip(), "cards": []})
            self._save()
            self._open_deck(len(self.data["decks"]) - 1)

    def _rename_deck(self):
        deck = self._deck()
        name = simpledialog.askstring("Rename deck", "New name:",
                                      initialvalue=deck["name"], parent=self)
        if name and name.strip():
            deck["name"] = name.strip()
            self._save()
            self._refresh_deck()

    def _delete_deck(self):
        deck = self._deck()
        if messagebox.askyesno("Delete deck",
                               f"Delete “{deck['name']}” and its {len(deck['cards'])} cards?",
                               parent=self):
            del self.data["decks"][self.deck_idx]
            self._save()
            self.deck_idx = None
            self.show("home")

    def _add_card(self):
        dlg = CardDialog(self, self.t, "Add card")
        if dlg.front or dlg.back:
            if not dlg.front or not dlg.back:
                messagebox.showwarning("Incomplete card",
                                       "Both front and back need text.", parent=self)
                return
            self._deck()["cards"].append({"front": dlg.front, "back": dlg.back})
            self._save()
            self._refresh_deck()

    def _edit_card_at_cursor(self):
        sel = self.card_list.curselection()
        if not sel:
            return
        card = self._deck()["cards"][sel[0]]
        dlg = CardDialog(self, self.t, "Edit card", card["front"], card["back"])
        if dlg.front and dlg.back:
            card["front"], card["back"] = dlg.front, dlg.back
            self._save()
            self._refresh_deck()

    def _import_txt(self):
        dlg = ImportDialog(self, self.t, [d["name"] for d in self.data["decks"]])
        self.wait_window(dlg)
        if not dlg.result:
            return
        target, cards = dlg.result
        if target[0] == "new":
            self.data["decks"].append({"name": target[1], "cards": cards})
            new_idx = len(self.data["decks"]) - 1
        else:
            new_idx = target[1]
            self.data["decks"][new_idx]["cards"].extend(cards)
        self._save()
        self._open_deck(new_idx)
        messagebox.showinfo("Imported", f"Added {len(cards)} cards.", parent=self)

    def _export_txt(self):
        ExportDialog(self, self.t, self._deck())


def main():
    FlashLite().mainloop()


if __name__ == "__main__":
    main()
