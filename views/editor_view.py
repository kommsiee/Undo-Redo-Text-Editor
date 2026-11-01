from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable, List, Tuple
from models.search import SearchResult


class CustomText(tk.Text):
    """Tkinter Text widget that intercepts insert and delete via Tcl proxy."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._orig = self._w + "_orig"
        self.tk.call("rename", self._w, self._orig)
        self.tk.createcommand(self._w, self._proxy)

    def _proxy(self, *args):
        cmd = args[0]
        try:
            result = self.tk.call(self._orig, *args)
        except tk.TclError:
            return ""

        if cmd in ("insert", "delete", "replace"):
            self.event_generate("<<TextModified>>", when="tail")
        elif cmd in ("mark", "set"):
            self.event_generate("<<CursorMoved>>", when="tail")

        return result


class EditorView:
    """Main application view with tabbed editing, menus, and status bar."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Stack-Based Undo/Redo Text Editor")
        self.root.geometry("1050x700")

        self._on_text_change_cb: Optional[Callable] = None
        self._on_undo_cb: Optional[Callable] = None
        self._on_redo_cb: Optional[Callable] = None
        self._on_save_cb: Optional[Callable] = None
        self._on_save_as_cb: Optional[Callable] = None
        self._on_open_cb: Optional[Callable] = None
        self._on_new_cb: Optional[Callable] = None
        self._on_find_cb: Optional[Callable] = None
        self._on_replace_cb: Optional[Callable] = None
        self._on_close_tab_cb: Optional[Callable] = None
        self._on_tab_changed_cb: Optional[Callable] = None
        self._on_macro_toggle_cb: Optional[Callable] = None
        self._on_macro_play_cb: Optional[Callable] = None
        self._on_buffer_type_cb: Optional[Callable] = None

        self._syntax_highlight_after_id: Optional[str] = None
        self._text_widgets: List[CustomText] = []

        self._build_menu()
        self._build_toolbar()
        self._build_main_area()
        self._build_history_panel()
        self._build_status_bar()
        self._bind_shortcuts()

    def _build_menu(self) -> None:
        self.menubar = tk.Menu(self.root)

        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.file_menu.add_command(label="New Tab", accelerator="Ctrl+N", command=lambda: self._trigger(self._on_new_cb))
        self.file_menu.add_command(label="Open...", accelerator="Ctrl+O", command=lambda: self._trigger(self._on_open_cb))
        self.file_menu.add_command(label="Save", accelerator="Ctrl+S", command=lambda: self._trigger(self._on_save_cb))
        self.file_menu.add_command(label="Save As...", accelerator="Ctrl+Shift+S", command=lambda: self._trigger(self._on_save_as_cb))
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Close Tab", accelerator="Ctrl+W", command=lambda: self._trigger(self._on_close_tab_cb))
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.root.quit)
        self.menubar.add_cascade(label="File", menu=self.file_menu)

        self.edit_menu = tk.Menu(self.menubar, tearoff=0)
        self.edit_menu.add_command(label="Undo", accelerator="Ctrl+Z", command=lambda: self._trigger(self._on_undo_cb))
        self.edit_menu.add_command(label="Redo", accelerator="Ctrl+Y", command=lambda: self._trigger(self._on_redo_cb))
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Cut", accelerator="Ctrl+X", command=lambda: self.root.focus_get().event_generate("<<Cut>>"))
        self.edit_menu.add_command(label="Copy", accelerator="Ctrl+C", command=lambda: self.root.focus_get().event_generate("<<Copy>>"))
        self.edit_menu.add_command(label="Paste", accelerator="Ctrl+V", command=lambda: self.root.focus_get().event_generate("<<Paste>>"))
        self.edit_menu.add_command(label="Select All", accelerator="Ctrl+A", command=self._select_all)
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Find...", accelerator="Ctrl+F", command=lambda: self._trigger(self._on_find_cb))
        self.edit_menu.add_command(label="Replace...", accelerator="Ctrl+H", command=lambda: self._trigger(self._on_replace_cb))
        self.menubar.add_cascade(label="Edit", menu=self.edit_menu)

        self.macro_menu = tk.Menu(self.menubar, tearoff=0)
        self.macro_menu.add_command(label="Record / Stop Macro", accelerator="Ctrl+Shift+R", command=lambda: self._trigger(self._on_macro_toggle_cb))
        self.macro_menu.add_command(label="Replay Macro", accelerator="Ctrl+Shift+P", command=lambda: self._trigger(self._on_macro_play_cb))
        self.menubar.add_cascade(label="Macro", menu=self.macro_menu)

        self.buffer_menu = tk.Menu(self.menubar, tearoff=0)
        self.buffer_var = tk.StringVar(value="piece_table")
        for b_name, b_label in [
            ("piece_table", "Piece Table (Default)"),
            ("gap", "Gap Buffer"),
            ("rope", "Rope (Binary Tree)"),
            ("string", "String Buffer (Baseline)"),
        ]:
            self.buffer_menu.add_radiobutton(
                label=b_label,
                variable=self.buffer_var,
                value=b_name,
                command=self._on_buffer_type_selected,
            )
        self.menubar.add_cascade(label="Buffer Structure", menu=self.buffer_menu)

        self.root.config(menu=self.menubar)

    def _build_toolbar(self) -> None:
        self.toolbar = ttk.Frame(self.root, padding=4)
        self.toolbar.pack(side="top", fill="x")

        ttk.Button(self.toolbar, text="New", width=6, command=lambda: self._trigger(self._on_new_cb)).pack(side="left", padx=2)
        ttk.Button(self.toolbar, text="Open", width=6, command=lambda: self._trigger(self._on_open_cb)).pack(side="left", padx=2)
        ttk.Button(self.toolbar, text="Save", width=6, command=lambda: self._trigger(self._on_save_cb)).pack(side="left", padx=2)
        ttk.Separator(self.toolbar, orient="vertical").pack(side="left", fill="y", padx=6)

        ttk.Button(self.toolbar, text="Undo", width=6, command=lambda: self._trigger(self._on_undo_cb)).pack(side="left", padx=2)
        ttk.Button(self.toolbar, text="Redo", width=6, command=lambda: self._trigger(self._on_redo_cb)).pack(side="left", padx=2)
        ttk.Separator(self.toolbar, orient="vertical").pack(side="left", fill="y", padx=6)

        ttk.Button(self.toolbar, text="Find", width=6, command=lambda: self._trigger(self._on_find_cb)).pack(side="left", padx=2)
        ttk.Button(self.toolbar, text="Replace", width=7, command=lambda: self._trigger(self._on_replace_cb)).pack(side="left", padx=2)
        ttk.Separator(self.toolbar, orient="vertical").pack(side="left", fill="y", padx=6)

        self.macro_btn = ttk.Button(self.toolbar, text="Record Macro", command=lambda: self._trigger(self._on_macro_toggle_cb))
        self.macro_btn.pack(side="left", padx=2)
        ttk.Button(self.toolbar, text="Play Macro", width=9, command=lambda: self._trigger(self._on_macro_play_cb)).pack(side="left", padx=2)

    def _build_main_area(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(side="top", fill="both", expand=True, padx=6, pady=2)
        self.notebook.bind("<<NotebookTabChanged>>", self._handle_tab_changed)

    def _build_history_panel(self) -> None:
        self.history_frame = ttk.LabelFrame(self.root, text="Edit History (Command Log)", padding=6)
        self.history_frame.pack(side="bottom", fill="x", padx=6, pady=4)

        hist_scroll = ttk.Scrollbar(self.history_frame, orient="vertical")
        self.history_list = tk.Listbox(self.history_frame, height=4, yscrollcommand=hist_scroll.set, font=("Courier", 10))
        hist_scroll.config(command=self.history_list.yview)
        hist_scroll.pack(side="right", fill="y")
        self.history_list.pack(side="left", fill="both", expand=True)

    def _build_status_bar(self) -> None:
        self.status_bar = ttk.Frame(self.root, relief="sunken", padding=4)
        self.status_bar.pack(side="bottom", fill="x")

        self.status_pos = ttk.Label(self.status_bar, text="Ln 1, Col 0")
        self.status_pos.pack(side="left", padx=8)

        self.status_modified = ttk.Label(self.status_bar, text="[Saved]", foreground="#006600")
        self.status_modified.pack(side="left", padx=8)

        self.status_buffer = ttk.Label(self.status_bar, text="Buffer: PieceTable")
        self.status_buffer.pack(side="left", padx=8)

        self.status_macro = ttk.Label(self.status_bar, text="", foreground="#aa0000")
        self.status_macro.pack(side="left", padx=8)

        self.status_search = ttk.Label(self.status_bar, text="", foreground="#555555")
        self.status_search.pack(side="right", padx=8)

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-n>", lambda e: self._trigger(self._on_new_cb))
        self.root.bind("<Control-o>", lambda e: self._trigger(self._on_open_cb))
        self.root.bind("<Control-s>", lambda e: self._trigger(self._on_save_cb))
        self.root.bind("<Control-Shift-S>", lambda e: self._trigger(self._on_save_as_cb))
        self.root.bind("<Control-w>", lambda e: self._trigger(self._on_close_tab_cb))
        self.root.bind("<Control-z>", lambda e: self._trigger(self._on_undo_cb))
        self.root.bind("<Control-y>", lambda e: self._trigger(self._on_redo_cb))
        self.root.bind("<Control-Shift-Z>", lambda e: self._trigger(self._on_redo_cb))
        self.root.bind("<Control-f>", lambda e: self._trigger(self._on_find_cb))
        self.root.bind("<Control-h>", lambda e: self._trigger(self._on_replace_cb))
        self.root.bind("<Control-Shift-R>", lambda e: self._trigger(self._on_macro_toggle_cb))
        self.root.bind("<Control-Shift-P>", lambda e: self._trigger(self._on_macro_play_cb))

    def _trigger(self, callback: Optional[Callable]) -> None:
        if callback:
            callback()

    def _select_all(self) -> None:
        text_w = self.get_active_text_widget()
        if text_w:
            text_w.tag_add("sel", "1.0", "end")

    def add_tab(self, title: str = "Untitled") -> int:
        frame = ttk.Frame(self.notebook)
        scroll_y = ttk.Scrollbar(frame, orient="vertical")
        scroll_x = ttk.Scrollbar(frame, orient="horizontal")

        text_widget = CustomText(
            frame,
            wrap="none",
            undo=False,
            font=("Menlo", 12) if "darwin" in self.root.tk.call("tk", "windowingsystem") else ("Consolas", 11),
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
        )
        scroll_y.config(command=text_widget.yview)
        scroll_x.config(command=text_widget.xview)

        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        text_widget.pack(side="left", fill="both", expand=True)

        self._configure_tags(text_widget)

        text_widget.bind("<<TextModified>>", self._handle_text_modified)
        text_widget.bind("<<CursorMoved>>", self._handle_cursor_moved)
        text_widget.bind("<KeyRelease>", self._handle_cursor_moved)
        text_widget.bind("<ButtonRelease-1>", self._handle_cursor_moved)

        self.notebook.add(frame, text=title)
        self._text_widgets.append(text_widget)

        idx = len(self._text_widgets) - 1
        self.notebook.select(idx)
        text_widget.focus_set()
        return idx

    def close_tab(self, index: int) -> None:
        if 0 <= index < len(self._text_widgets):
            self.notebook.forget(index)
            self._text_widgets.pop(index)

    def get_active_tab_index(self) -> int:
        try:
            return self.notebook.index(self.notebook.select())
        except Exception:
            return -1

    def set_tab_title(self, index: int, title: str) -> None:
        if 0 <= index < len(self._text_widgets):
            self.notebook.tab(index, text=title)

    def get_active_text_widget(self) -> Optional[CustomText]:
        idx = self.get_active_tab_index()
        if 0 <= idx < len(self._text_widgets):
            return self._text_widgets[idx]
        return None

    def _configure_tags(self, w: CustomText) -> None:
        w.tag_configure("search_match", background="#fff275", foreground="#000000")
        w.tag_configure("current_match", background="#ff9f1c", foreground="#ffffff")
        w.tag_configure("syntax_keyword", foreground="#0000ff", font=(w.cget("font"), "bold"))
        w.tag_configure("syntax_string", foreground="#a31515")
        w.tag_configure("syntax_comment", foreground="#008000", font=(w.cget("font"), "italic"))
        w.tag_configure("syntax_number", foreground="#098658")

    def schedule_syntax_highlight(self) -> None:
        if self._syntax_highlight_after_id:
            self.root.after_cancel(self._syntax_highlight_after_id)
        self._syntax_highlight_after_id = self.root.after(250, self._apply_syntax_highlight)

    def _apply_syntax_highlight(self) -> None:
        w = self.get_active_text_widget()
        if not w:
            return

        text = w.get("1.0", "end-1c")
        if len(text) > 200000:
            return

        for tag in ("syntax_keyword", "syntax_string", "syntax_comment", "syntax_number"):
            w.tag_remove(tag, "1.0", "end")

        keywords = {
            "def", "class", "if", "elif", "else", "for", "while", "return", "import", "from",
            "as", "try", "except", "finally", "with", "yield", "lambda", "pass", "break",
            "continue", "True", "False", "None", "self", "async", "await", "global", "nonlocal",
            "function", "const", "let", "var", "switch", "case", "new", "this"
        }

        for m in re.finditer(r"#[^\n]*", text):
            w.tag_add("syntax_comment", f"1.0 + {m.start()}c", f"1.0 + {m.end()}c")

        for m in re.finditer(r'("[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\')', text):
            w.tag_add("syntax_string", f"1.0 + {m.start()}c", f"1.0 + {m.end()}c")

        for m in re.finditer(r"\b\d+(?:\.\d+)?\b", text):
            w.tag_add("syntax_number", f"1.0 + {m.start()}c", f"1.0 + {m.end()}c")

        for m in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_]*\b", text):
            if m.group() in keywords:
                w.tag_add("syntax_keyword", f"1.0 + {m.start()}c", f"1.0 + {m.end()}c")

    def highlight_matches(self, matches: List[SearchResult]) -> None:
        w = self.get_active_text_widget()
        if not w:
            return
        w.tag_remove("search_match", "1.0", "end")
        w.tag_remove("current_match", "1.0", "end")

        for m in matches:
            w.tag_add("search_match", f"1.0 + {m.start}c", f"1.0 + {m.end}c")

    def highlight_current_match(self, match: SearchResult) -> None:
        w = self.get_active_text_widget()
        if not w:
            return
        w.tag_remove("current_match", "1.0", "end")
        start_idx = f"1.0 + {match.start}c"
        end_idx = f"1.0 + {match.end}c"
        w.tag_add("current_match", start_idx, end_idx)
        w.see(start_idx)

    def clear_highlights(self) -> None:
        w = self.get_active_text_widget()
        if not w:
            return
        w.tag_remove("search_match", "1.0", "end")
        w.tag_remove("current_match", "1.0", "end")

    def get_text(self) -> str:
        w = self.get_active_text_widget()
        if not w:
            return ""
        return w.get("1.0", "end-1c")

    def set_text(self, text: str) -> None:
        w = self.get_active_text_widget()
        if not w:
            return
        w.delete("1.0", "end")
        w.insert("1.0", text)
        self.schedule_syntax_highlight()

    def get_cursor_position(self) -> int:
        w = self.get_active_text_widget()
        if not w:
            return 0
        return len(w.get("1.0", tk.INSERT))

    def set_cursor_position(self, pos: int) -> None:
        w = self.get_active_text_widget()
        if not w:
            return
        idx = f"1.0 + {pos}c"
        w.mark_set(tk.INSERT, idx)
        w.see(idx)

    def get_selection(self) -> Optional[Tuple[int, int]]:
        w = self.get_active_text_widget()
        if not w:
            return None
        try:
            sel_start = len(w.get("1.0", tk.SEL_FIRST))
            sel_end = len(w.get("1.0", tk.SEL_LAST))
            return sel_start, sel_end
        except tk.TclError:
            return None

    def update_status(self, line: int, col: int, modified: bool, buffer_type: str) -> None:
        self.status_pos.config(text=f"Ln {line}, Col {col}")
        if modified:
            self.status_modified.config(text="[Modified *]", foreground="#cc0000")
        else:
            self.status_modified.config(text="[Saved]", foreground="#006600")
        self.status_buffer.config(text=f"Buffer: {buffer_type.capitalize()}")

    def update_history(self, entries: List[str]) -> None:
        self.history_list.delete(0, "end")
        for item in reversed(entries[-20:]):
            self.history_list.insert("end", item)

    def update_macro_status(self, recording: bool) -> None:
        if recording:
            self.status_macro.config(text="● RECORDING MACRO")
            self.macro_btn.config(text="Stop Macro")
        else:
            self.status_macro.config(text="")
            self.macro_btn.config(text="Record Macro")

    def _handle_text_modified(self, event=None) -> None:
        self.schedule_syntax_highlight()
        if self._on_text_change_cb:
            self._on_text_change_cb()

    def _handle_cursor_moved(self, event=None) -> None:
        w = self.get_active_text_widget()
        if not w:
            return
        line, col = w.index(tk.INSERT).split(".")
        self.status_pos.config(text=f"Ln {line}, Col {col}")

    def _handle_tab_changed(self, event=None) -> None:
        if self._on_tab_changed_cb:
            self._on_tab_changed_cb()

    def _on_buffer_type_selected(self) -> None:
        if self._on_buffer_type_cb:
            self._on_buffer_type_cb(self.buffer_var.get())

    def on_text_change(self, cb: Callable) -> None: self._on_text_change_cb = cb
    def on_undo(self, cb: Callable) -> None: self._on_undo_cb = cb
    def on_redo(self, cb: Callable) -> None: self._on_redo_cb = cb
    def on_save(self, cb: Callable) -> None: self._on_save_cb = cb
    def on_save_as(self, cb: Callable) -> None: self._on_save_as_cb = cb
    def on_open(self, cb: Callable) -> None: self._on_open_cb = cb
    def on_new(self, cb: Callable) -> None: self._on_new_cb = cb
    def on_find(self, cb: Callable) -> None: self._on_find_cb = cb
    def on_replace(self, cb: Callable) -> None: self._on_replace_cb = cb
    def on_close_tab(self, cb: Callable) -> None: self._on_close_tab_cb = cb
    def on_tab_changed(self, cb: Callable) -> None: self._on_tab_changed_cb = cb
    def on_macro_toggle(self, cb: Callable) -> None: self._on_macro_toggle_cb = cb
    def on_macro_play(self, cb: Callable) -> None: self._on_macro_play_cb = cb
    def on_buffer_type_change(self, cb: Callable) -> None: self._on_buffer_type_cb = cb
