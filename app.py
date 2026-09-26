"""FlashLite - a tiny, lightweight flashcard app.

Single exe, no account, no cloud. Decks are stored in flashlite_data.json
next to the exe. Inspired by Flashbang's minimalism.
"""
import random
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

import flashcards as fc

try:
    from version import VERSION  # stamped at build time by the release workflow
except Exception:
    VERSION = "dev"

REPO_URL = "https://github.com/kappytappy/flashlite"
RELEASES_URL = REPO_URL + "/releases"


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
# Dialogs
# --------------------------------------------------------------------------- #
class CardDialog(simpledialog.Dialog):
    """Add / edit a single card (front + back)."""

    def __init__(self, parent, title, front="", back=""):
        self.front = front
        self.back = back
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text="Front:").grid(row=0, column=0, sticky="w")
        self.front_txt = tk.Text(master, width=48, height=4, wrap="word")
        self.front_txt.grid(row=1, column=0, padx=5, pady=(0, 8))
        self.front_txt.insert("1.0", self.front)
        ttk.Label(master, text="Back:").grid(row=2, column=0, sticky="w")
        self.back_txt = tk.Text(master, width=48, height=4, wrap="word")
        self.back_txt.grid(row=3, column=0, padx=5, pady=(0, 5))
        self.back_txt.insert("1.0", self.back)
        return self.front_txt

    def apply(self):
        self.front = self.front_txt.get("1.0", "end").strip()
        self.back = self.back_txt.get("1.0", "end").strip()


class ImportDialog(tk.Toplevel):
    """Import cards from a .txt file: pick file, separator, target deck, preview."""

    SEP_LABELS = [("Tab", "tab"), ("Pipe  |", "pipe"), ("Semicolon  ;", "semicolon"),
                  ("Comma  ,", "comma"), ("Custom", "custom")]

    def __init__(self, parent, deck_names):
        super().__init__(parent)
        self.title("Import cards from .txt")
        self.resizable(False, False)
        self.result = None  # (("new", name) | ("existing", idx), cards)
        self._deck_names = deck_names

        self.file_var = tk.StringVar()
        self.sep_var = tk.StringVar(value="pipe")
        self.custom_var = tk.StringVar(value=":")
        self.target_var = tk.StringVar(value="new")
        self.newname_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Pick a .txt file to begin.")
        self._cards = []

        frm = ttk.Frame(self, padding=12)
        frm.grid(sticky="nsew")

        # File row
        ttk.Label(frm, text="File:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.file_var, width=44).grid(row=0, column=1, padx=5)
        ttk.Button(frm, text="Browse…", command=self._browse).grid(row=0, column=2)

        # Separator row
        ttk.Label(frm, text="Separator:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        sepfrm = ttk.Frame(frm)
        sepfrm.grid(row=1, column=1, columnspan=2, sticky="w", pady=(8, 0))
        for label, key in self.SEP_LABELS:
            ttk.Radiobutton(sepfrm, text=label, value=key, variable=self.sep_var,
                            command=self._reparse).pack(side="left", padx=(0, 6))
        self.custom_entry = ttk.Entry(sepfrm, textvariable=self.custom_var, width=4)
        self.custom_entry.pack(side="left")
        self.custom_var.trace_add("write", lambda *a: self._reparse())

        # Target deck row
        ttk.Label(frm, text="Add to:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        tgtfrm = ttk.Frame(frm)
        tgtfrm.grid(row=2, column=1, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Radiobutton(tgtfrm, text="New deck:", value="new",
                        variable=self.target_var).pack(side="left")
        self.newname_entry = ttk.Entry(tgtfrm, textvariable=self.newname_var, width=20)
        self.newname_entry.pack(side="left", padx=5)
        ttk.Radiobutton(tgtfrm, text="Existing:", value="existing",
                        variable=self.target_var).pack(side="left", padx=(8, 0))
        self.existing_combo = ttk.Combobox(tgtfrm, values=deck_names, width=18,
                                           state="readonly")
        self.existing_combo.pack(side="left", padx=5)
        if deck_names:
            self.existing_combo.current(0)

        # Preview
        ttk.Label(frm, text="Preview:").grid(row=3, column=0, sticky="nw", pady=(8, 0))
        self.preview = tk.Listbox(frm, width=62, height=8)
        self.preview.grid(row=3, column=1, columnspan=2, pady=(8, 0))
        ttk.Label(frm, textvariable=self.status_var, foreground="gray").grid(
            row=4, column=1, columnspan=2, sticky="w", pady=(4, 0))

        # Buttons
        btnfrm = ttk.Frame(frm)
        btnfrm.grid(row=5, column=1, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btnfrm, text="Import", command=self._do_import).pack(side="left", padx=5)
        ttk.Button(btnfrm, text="Cancel", command=self.destroy).pack(side="left")

        self.transient(parent)
        self.grab_set()

    # -- internals ---------------------------------------------------------- #
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
            front = card["front"][:34]
            back = card["back"][:34]
            self.preview.insert("end", f"{front}  →  {back}")
        if len(cards) > 15:
            self.preview.insert("end", f"… and {len(cards) - 15} more")
        msg = f"{len(cards)} card(s) ready"
        if skipped:
            msg += f", {skipped} line(s) skipped (no separator or empty side)"
        self.status_var.set(msg)

    def _do_import(self):
        if not self._cards:
            messagebox.showwarning("Nothing to import",
                                   "No cards were parsed. Check the file and separator.",
                                   parent=self)
            return
        if self.target_var.get() == "new":
            name = self.newname_var.get().strip()
            if not name:
                messagebox.showwarning("Name needed",
                                       "Give the new deck a name.", parent=self)
                return
            target = ("new", name)
        else:
            if not self._deck_names:
                messagebox.showwarning("No decks",
                                       "There are no existing decks yet.", parent=self)
                return
            target = ("existing", self.existing_combo.current())
        self.result = (target, self._cards)
        self.destroy()


class ExportDialog(tk.Toplevel):
    """Export the current deck to .txt with a chosen separator."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Export deck to .txt")
        self.resizable(False, False)
        self.sep_var = tk.StringVar(value="pipe")

        frm = ttk.Frame(self, padding=12)
        frm.grid(sticky="nsew")
        ttk.Label(frm, text="Separator:").grid(row=0, column=0, sticky="w")
        sepfrm = ttk.Frame(frm)
        sepfrm.grid(row=0, column=1, sticky="w")
        for label, key in [("Tab", "tab"), ("Pipe  |", "pipe"),
                           ("Semicolon  ;", "semicolon"), ("Comma  ,", "comma")]:
            ttk.Radiobutton(sepfrm, text=label, value=key,
                            variable=self.sep_var).pack(side="left", padx=(0, 6))
        btnfrm = ttk.Frame(frm)
        btnfrm.grid(row=1, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btnfrm, text="Save…", command=self._save).pack(side="left", padx=5)
        ttk.Button(btnfrm, text="Cancel", command=self.destroy).pack(side="left")
        self.transient(parent)
        self.grab_set()
        self._deck = None

    def _save(self):
        path = filedialog.asksaveasfilename(
            title="Save deck as .txt", defaultextension=".txt",
            filetypes=[("Text files", "*.txt")], parent=self)
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(fc.deck_to_txt(self._deck, fc.SEPARATORS[self.sep_var.get()]))
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)
            return
        messagebox.showinfo("Exported", f"Saved {len(self._deck['cards'])} cards.",
                            parent=self)
        self.destroy()


# --------------------------------------------------------------------------- #
# Study windows
# --------------------------------------------------------------------------- #
class StudyBase(tk.Toplevel):
    """Shared bits: shuffled cards, progress, score, finish dialog."""

    def __init__(self, parent, deck, title):
        super().__init__(parent)
        self.title(f"{title} — {deck['name']}")
        self.geometry("560x440")
        self.deck = deck
        self.cards = deck["cards"][:]
        random.shuffle(self.cards)
        self.idx = 0
        self.score = 0
        self.total = len(self.cards)
        self.progress_var = tk.StringVar()
        self.score_var = tk.StringVar(value="")

    def _refresh_progress(self):
        self.progress_var.set(f"Card {self.idx + 1} of {self.total}")
        self.score_var.set(f"Score: {self.score}/{self.idx}")

    def _finish(self):
        messagebox.showinfo("Done!",
                            f"Finished “{self.deck['name']}”\nScore: {self.score}/{self.total}",
                            parent=self)
        self.destroy()


class ReviewWindow(StudyBase):
    """Classic flashcard review: look, flip, next."""

    def __init__(self, parent, deck):
        super().__init__(parent, deck, "Review")
        self.flipped = False

        ttk.Label(self, textvariable=self.progress_var,
                  font=("Segoe UI", 10)).pack(pady=(10, 2))
        self.face = tk.Label(self, text="", font=("Segoe UI", 20), wraplength=480,
                             height=6, relief="ridge", bd=2, bg="white")
        self.face.pack(padx=20, pady=10, fill="both", expand=True)
        self.face.bind("<Button-1>", lambda e: self._flip())

        mid = ttk.Frame(self)
        mid.pack(pady=5)
        ttk.Button(mid, text="◀ Prev", command=self._prev).pack(side="left", padx=5)
        ttk.Button(mid, text="Flip (Space)", command=self._flip).pack(side="left", padx=5)
        ttk.Button(mid, text="🔊 Read aloud", command=self._speak).pack(side="left", padx=5)
        ttk.Button(mid, text="Next ▶", command=self._next).pack(side="left", padx=5)

        ttk.Label(self, textvariable=self.score_var).pack(pady=(0, 10))

        self.bind("<Left>", lambda e: self._prev())
        self.bind("<Right>", lambda e: self._next())
        self.bind("<space>", lambda e: self._flip())
        self._show()

    def _show(self):
        self._refresh_progress()
        card = self.cards[self.idx]
        self.face.config(text=card["front"] if not self.flipped else card["back"])

    def _flip(self):
        self.flipped = not self.flipped
        self._show()

    def _speak(self):
        card = self.cards[self.idx]
        speak(card["back"] if self.flipped else card["front"])

    def _prev(self):
        if self.idx > 0:
            self.idx -= 1
            self.flipped = False
            self._show()

    def _next(self):
        if self.idx < self.total - 1:
            self.idx += 1
            self.flipped = False
            self._show()


class TypingWindow(StudyBase):
    """Typing mode: see the front, type the back."""

    def __init__(self, parent, deck):
        super().__init__(parent, deck, "Typing test")
        self.answered = False

        ttk.Label(self, textvariable=self.progress_var,
                  font=("Segoe UI", 10)).pack(pady=(10, 2))
        self.front_lbl = tk.Label(self, text="", font=("Segoe UI", 18), wraplength=480,
                                  height=4, relief="ridge", bd=2, bg="white")
        self.front_lbl.pack(padx=20, pady=10, fill="x")
        ttk.Label(self, text="Type the answer:").pack()
        self.answer = ttk.Entry(self, width=50, font=("Segoe UI", 12))
        self.answer.pack(pady=5)
        self.answer.bind("<Return>", lambda e: self._check())
        self.feedback = tk.Label(self, text="", font=("Segoe UI", 12), wraplength=480,
                                 height=3)
        self.feedback.pack(pady=5)

        btns = ttk.Frame(self)
        btns.pack(pady=5)
        self.check_btn = ttk.Button(btns, text="Check", command=self._check)
        self.check_btn.pack(side="left", padx=5)
        self.next_btn = ttk.Button(btns, text="Next ▶", command=self._next,
                                   state="disabled")
        self.next_btn.pack(side="left", padx=5)
        ttk.Label(self, textvariable=self.score_var).pack(pady=(5, 10))
        self._show()

    def _show(self):
        self._refresh_progress()
        self.answered = False
        self.front_lbl.config(text=self.cards[self.idx]["front"])
        self.answer.delete(0, "end")
        self.answer.config(state="normal")
        self.feedback.config(text="")
        self.check_btn.config(state="normal")
        self.next_btn.config(state="disabled")
        self.answer.focus_set()

    def _check(self):
        if self.answered:
            return
        self.answered = True
        given = self.answer.get().strip().lower()
        want = self.cards[self.idx]["back"].strip().lower()
        if given and given == want:
            self.score += 1
            self.feedback.config(text="✔ Correct!", foreground="green")
        else:
            self.feedback.config(
                text=f"✘ Wrong — the answer was:\n{self.cards[self.idx]['back']}",
                foreground="red")
        self.answer.config(state="disabled")
        self.check_btn.config(state="disabled")
        self.next_btn.config(state="normal")
        self.next_btn.focus_set()
        self._refresh_progress()

    def _next(self):
        if self.idx < self.total - 1:
            self.idx += 1
            self._show()
        else:
            self._finish()


class TestWindow(StudyBase):
    """Test mode: multiple choice, 4 options."""

    def __init__(self, parent, deck):
        super().__init__(parent, deck, "Multiple choice")
        self.answered = False

        ttk.Label(self, textvariable=self.progress_var,
                  font=("Segoe UI", 10)).pack(pady=(10, 2))
        self.front_lbl = tk.Label(self, text="", font=("Segoe UI", 18), wraplength=480,
                                  height=3, relief="ridge", bd=2, bg="white")
        self.front_lbl.pack(padx=20, pady=10, fill="x")
        self.opt_frame = ttk.Frame(self)
        self.opt_frame.pack(pady=5, fill="x", padx=40)
        self.opt_buttons = []
        for i in range(4):
            btn = tk.Button(self.opt_frame, text="", font=("Segoe UI", 12),
                            wraplength=420, anchor="w", justify="left",
                            command=lambda i=i: self._pick(i))
            btn.pack(fill="x", pady=3)
            self.opt_buttons.append(btn)
        self.next_btn = ttk.Button(self, text="Next ▶", command=self._next,
                                   state="disabled")
        self.next_btn.pack(pady=5)
        ttk.Label(self, textvariable=self.score_var).pack(pady=(5, 10))
        self._show()

    def _show(self):
        self._refresh_progress()
        self.answered = False
        card = self.cards[self.idx]
        self.front_lbl.config(text=card["front"])
        correct = card["back"]
        pool = [c["back"] for c in self.deck["cards"]
                if c["back"] != correct]
        random.shuffle(pool)
        options = [correct] + pool[:3]
        random.shuffle(options)
        self._options = options
        self._correct_idx = options.index(correct)
        for btn, opt in zip(self.opt_buttons, options):
            btn.config(text=opt, state="normal", bg="SystemButtonFace")
        for btn in self.opt_buttons[len(options):]:
            btn.config(text="", state="disabled", bg="SystemButtonFace")
        self.next_btn.config(state="disabled")

    def _pick(self, i):
        if self.answered:
            return
        self.answered = True
        for btn in self.opt_buttons:
            btn.config(state="disabled")
        if i == self._correct_idx:
            self.score += 1
            self.opt_buttons[i].config(bg="#b6e6b6")
        else:
            self.opt_buttons[i].config(bg="#f2b8b8")
            self.opt_buttons[self._correct_idx].config(bg="#b6e6b6")
        self.next_btn.config(state="normal")
        self._refresh_progress()

    def _next(self):
        if self.idx < self.total - 1:
            self.idx += 1
            self._show()
        else:
            self._finish()


# --------------------------------------------------------------------------- #
# Main window
# --------------------------------------------------------------------------- #
class FlashLite(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"FlashLite {VERSION}")
        self.geometry("780x540")
        self.minsize(640, 440)

        self.data = fc.load()
        if not self.data["decks"]:
            self.data["decks"].append({
                "name": "Example",
                "cards": [
                    {"front": "Capital of France?", "back": "Paris"},
                    {"front": "2 + 2 = ?", "back": "4"},
                    {"front": "Largest planet in the solar system?", "back": "Jupiter"},
                ],
            })
            fc.save(self.data)

        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=8)

        # ---- left: decks ---- #
        left = ttk.Frame(paned, padding=6)
        ttk.Label(left, text="Decks", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.deck_list = tk.Listbox(left, width=28, exportselection=False)
        self.deck_list.pack(fill="both", expand=True, pady=5)
        self.deck_list.bind("<<ListboxSelect>>", lambda e: self._on_deck_select())

        deckbtns = ttk.Frame(left)
        deckbtns.pack(fill="x")
        ttk.Button(deckbtns, text="New", command=self._new_deck).pack(side="left", padx=2)
        ttk.Button(deckbtns, text="Rename", command=self._rename_deck).pack(side="left", padx=2)
        ttk.Button(deckbtns, text="Delete", command=self._delete_deck).pack(side="left", padx=2)

        iobtns = ttk.Frame(left)
        iobtns.pack(fill="x", pady=(6, 0))
        ttk.Button(iobtns, text="Import .txt…", command=self._import_txt).pack(
            side="left", padx=2, fill="x", expand=True)
        ttk.Button(iobtns, text="Export .txt…", command=self._export_txt).pack(
            side="left", padx=2, fill="x", expand=True)

        # ---- right: cards ---- #
        right = ttk.Frame(paned, padding=6)
        self.cards_title = tk.StringVar(value="Cards")
        ttk.Label(right, textvariable=self.cards_title,
                  font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.card_list = tk.Listbox(right, exportselection=False)
        self.card_list.pack(fill="both", expand=True, pady=5)

        cardbtns = ttk.Frame(right)
        cardbtns.pack(fill="x")
        ttk.Button(cardbtns, text="Add card", command=self._add_card).pack(side="left", padx=2)
        ttk.Button(cardbtns, text="Edit card", command=self._edit_card).pack(side="left", padx=2)
        ttk.Button(cardbtns, text="Delete card", command=self._delete_card).pack(side="left", padx=2)

        study = ttk.LabelFrame(right, text="Study this deck", padding=6)
        study.pack(fill="x", pady=(8, 0))
        self.review_btn = ttk.Button(study, text="📖 Review", command=self._review)
        self.review_btn.pack(side="left", padx=4, fill="x", expand=True)
        self.typing_btn = ttk.Button(study, text="⌨ Typing", command=self._typing)
        self.typing_btn.pack(side="left", padx=4, fill="x", expand=True)
        self.test_btn = ttk.Button(study, text="✓ Test", command=self._test)
        self.test_btn.pack(side="left", padx=4, fill="x", expand=True)

        paned.add(left, weight=1)
        paned.add(right, weight=3)

        # ---- status bar ---- #
        status = ttk.Frame(self)
        status.pack(fill="x", padx=8, pady=(0, 6))
        self.status_var = tk.StringVar(value="Pick a deck, or import a .txt file to start.")
        ttk.Label(status, textvariable=self.status_var, foreground="gray").pack(side="left")
        ttk.Label(status, text=f"v{VERSION}", foreground="gray").pack(side="right", padx=8)
        ttk.Button(status, text="Check for updates",
                   command=lambda: webbrowser.open(RELEASES_URL)).pack(side="right")

        self._refresh_decks()
        if self.data["decks"]:
            self.deck_list.selection_set(0)
            self._on_deck_select()

    # -- helpers ------------------------------------------------------------ #
    def _save(self):
        fc.save(self.data)

    def _sel_deck_idx(self):
        sel = self.deck_list.curselection()
        return sel[0] if sel else None

    def _sel_deck(self):
        idx = self._sel_deck_idx()
        return self.data["decks"][idx] if idx is not None else None

    def _refresh_decks(self):
        self.deck_list.delete(0, "end")
        for deck in self.data["decks"]:
            n = len(deck["cards"])
            self.deck_list.insert("end", f"{deck['name']}  ({n})")

    def _refresh_cards(self):
        self.card_list.delete(0, "end")
        deck = self._sel_deck()
        if not deck:
            self.cards_title.set("Cards")
            self._set_study_enabled(False)
            return
        self.cards_title.set(f"Cards — {deck['name']} ({len(deck['cards'])})")
        for card in deck["cards"]:
            front = card["front"].replace("\n", " ")
            back = card["back"].replace("\n", " ")
            if len(front) > 32:
                front = front[:32] + "…"
            if len(back) > 32:
                back = back[:32] + "…"
            self.card_list.insert("end", f"{front}  →  {back}")
        self._set_study_enabled(len(deck["cards"]) > 0)

    def _set_study_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        self.review_btn.config(state=state)
        self.typing_btn.config(state=state)
        # Test mode needs at least 2 cards for wrong options to make sense.
        deck = self._sel_deck()
        self.test_btn.config(state="normal" if enabled and deck and len(deck["cards"]) >= 2
                             else "disabled")

    def _on_deck_select(self):
        self._refresh_cards()

    # -- deck ops ----------------------------------------------------------- #
    def _new_deck(self):
        name = simpledialog.askstring("New deck", "Deck name:", parent=self)
        if name and name.strip():
            name = name.strip()
            self.data["decks"].append({"name": name, "cards": []})
            self._save()
            self._refresh_decks()
            self.deck_list.selection_clear(0, "end")
            self.deck_list.selection_set(len(self.data["decks"]) - 1)
            self._on_deck_select()
            self.status_var.set(f"Created deck “{name}”. Add cards or import a .txt file.")

    def _rename_deck(self):
        deck = self._sel_deck()
        if not deck:
            return
        name = simpledialog.askstring("Rename deck", "New name:",
                                      initialvalue=deck["name"], parent=self)
        if name and name.strip():
            deck["name"] = name.strip()
            self._save()
            idx = self._sel_deck_idx()
            self._refresh_decks()
            self.deck_list.selection_set(idx)
            self._on_deck_select()

    def _delete_deck(self):
        idx = self._sel_deck_idx()
        deck = self._sel_deck()
        if deck is None:
            return
        if messagebox.askyesno("Delete deck",
                               f"Delete “{deck['name']}” and its {len(deck['cards'])} cards?",
                               parent=self):
            del self.data["decks"][idx]
            self._save()
            self._refresh_decks()
            if self.data["decks"]:
                self.deck_list.selection_set(min(idx, len(self.data["decks"]) - 1))
            self._on_deck_select()

    # -- card ops ----------------------------------------------------------- #
    def _sel_card_idx(self):
        sel = self.card_list.curselection()
        return sel[0] if sel else None

    def _add_card(self):
        deck = self._sel_deck()
        if not deck:
            messagebox.showinfo("No deck", "Create or pick a deck first.", parent=self)
            return
        dlg = CardDialog(self, "Add card")
        if dlg.front or dlg.back:
            if not dlg.front or not dlg.back:
                messagebox.showwarning("Incomplete card",
                                       "Both front and back need text.", parent=self)
                return
            deck["cards"].append({"front": dlg.front, "back": dlg.back})
            self._save()
            self._refresh_decks()
            self.deck_list.selection_set(self._sel_deck_idx())
            self._refresh_cards()

    def _edit_card(self):
        deck = self._sel_deck()
        cidx = self._sel_card_idx()
        if deck is None or cidx is None:
            return
        card = deck["cards"][cidx]
        dlg = CardDialog(self, "Edit card", card["front"], card["back"])
        if dlg.front and dlg.back:
            card["front"], card["back"] = dlg.front, dlg.back
            self._save()
            self._refresh_cards()
            self.card_list.selection_set(cidx)

    def _delete_card(self):
        deck = self._sel_deck()
        cidx = self._sel_card_idx()
        if deck is None or cidx is None:
            return
        del deck["cards"][cidx]
        self._save()
        self._refresh_decks()
        self.deck_list.selection_set(self._sel_deck_idx())
        self._refresh_cards()

    # -- import / export ------------------------------------------------------ #
    def _import_txt(self):
        dlg = ImportDialog(self, [d["name"] for d in self.data["decks"]])
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
        self._refresh_decks()
        self.deck_list.selection_clear(0, "end")
        self.deck_list.selection_set(new_idx)
        self._on_deck_select()
        self.status_var.set(f"Imported {len(cards)} cards into "
                            f"“{self.data['decks'][new_idx]['name']}”.")
        messagebox.showinfo("Imported", f"Added {len(cards)} cards.", parent=self)

    def _export_txt(self):
        deck = self._sel_deck()
        if not deck:
            return
        dlg = ExportDialog(self)
        dlg._deck = deck

    # -- study modes ---------------------------------------------------------- #
    def _review(self):
        deck = self._sel_deck()
        if deck and deck["cards"]:
            ReviewWindow(self, deck)

    def _typing(self):
        deck = self._sel_deck()
        if deck and deck["cards"]:
            TypingWindow(self, deck)

    def _test(self):
        deck = self._sel_deck()
        if deck and len(deck["cards"]) >= 2:
            TestWindow(self, deck)


def main():
    FlashLite().mainloop()


if __name__ == "__main__":
    main()
