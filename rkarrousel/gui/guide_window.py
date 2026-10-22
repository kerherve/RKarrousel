"""Fenêtre « Guide » : liste des rubriques à gauche, texte de la rubrique à droite."""
import tkinter as tk
from tkinter import ttk

from rkarrousel.i18n import t
from rkarrousel.i18n.guide import get_guide


class GuideWindow(tk.Toplevel):
    def __init__(self, parent: tk.Misc, start_topic: str = None):
        super().__init__(parent)
        self.title(t("guide_title"))
        scale = max(1.0, self.winfo_fpixels("1i") / 96)
        width, height = int(860 * scale), int(600 * scale)
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 2 - 30)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(int(560 * scale), int(360 * scale))
        self.intro, self.topics = get_guide()

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(body, exportselection=False, activestyle="none", width=26, relief=tk.FLAT,
                                  borderwidth=1, highlightthickness=0, font=("Segoe UI", 10))
        self.listbox.grid(row=0, column=0, sticky=tk.NS, padx=(0, 12))
        for _, title, _ in self.topics:
            self.listbox.insert(tk.END, "  " + title)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        self.text = tk.Text(body, wrap=tk.WORD, relief=tk.FLAT, borderwidth=0, padx=14, pady=10,
                            font=("Segoe UI", 10), cursor="arrow", spacing3=4)
        scroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.grid(row=0, column=1, sticky=tk.NSEW)
        scroll.grid(row=0, column=2, sticky=tk.NS)
        self._configure_tags()

        self.bind("<Escape>", lambda _e: self.destroy())
        index = next((i for i, (tid, _, _) in enumerate(self.topics) if tid == start_topic), 0)
        self.show_topic(index)

    def _configure_tags(self) -> None:
        text = self.text
        text.tag_configure("title", font=("Segoe UI", 15, "bold"), spacing3=8)
        text.tag_configure("h", font=("Segoe UI", 11, "bold"), spacing1=8)
        text.tag_configure("code", font=("Consolas", 10), background="#e6e6e6", foreground="#222222")
        text.tag_configure("note", lmargin1=12, lmargin2=12, foreground="#555555", font=("Segoe UI", 10, "italic"))
        text.tag_configure("item", lmargin1=14, lmargin2=34)
        text.tag_configure("intro", foreground="#666666")

    def _on_select(self, _event=None) -> None:
        selection = self.listbox.curselection()
        if selection:
            self.show_topic(selection[0])

    def show_topic(self, index: int) -> None:
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(index)
        self.listbox.see(index)
        _, title, blocks = self.topics[index]
        text = self.text
        text.configure(state=tk.NORMAL)
        text.delete("1.0", tk.END)
        text.insert(tk.END, title + "\n", "title")
        for kind, content in blocks:
            if kind == "p":
                self._insert(content + "\n")
            elif kind == "h":
                self._insert(content + "\n", "h")
            elif kind == "note":
                self._insert(content + "\n", "note")
            elif kind == "bullets":
                for item in content:
                    self._insert("•  " + item + "\n", "item")
            elif kind == "steps":
                for number, item in enumerate(content, 1):
                    self._insert(f"{number}.  {item}\n", "item")
        text.configure(state=tk.DISABLED)
        text.yview_moveto(0)

    def _insert(self, line: str, tag: str = None) -> None:
        """Insère une ligne en mettant en police fixe les passages entre `accents graves`."""
        for number, chunk in enumerate(line.split("`")):
            tags = ((tag,) if tag else ()) + (("code",) if number % 2 else ())
            self.text.insert(tk.END, chunk, tags)
