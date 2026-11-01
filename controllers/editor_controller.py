from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional, List

from models.buffer import BUFFER_TYPES, PieceTable, TextBuffer
from models.commands import Command, InsertCommand, DeleteCommand, ReplaceCommand
from models.document import Document
from models.search import SearchEngine, SearchResult
from views.editor_view import EditorView
from views.search_dialog import SearchDialog
from views.tab_view import TabState


class EditorController:
    """Coordinates state changes between Document models and EditorView."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.view = EditorView(root)
        self.tabs: List[TabState] = []
        self.current_buffer_key: str = "piece_table"
        self.search_dialog: Optional[SearchDialog] = None
        self._syncing: bool = False

        self._bind_callbacks()
        self._new_tab(title="Untitled-1")

    @property
    def active_tab(self) -> Optional[TabState]:
        idx = self.view.get_active_tab_index()
        if 0 <= idx < len(self.tabs):
            return self.tabs[idx]
        return None

    def _bind_callbacks(self) -> None:
        self.view.on_text_change(self._on_text_change)
        self.view.on_undo(self._on_undo)
        self.view.on_redo(self._on_redo)
        self.view.on_new(self._on_new)
        self.view.on_open(self._on_open)
        self.view.on_save(self._on_save)
        self.view.on_save_as(self._on_save_as)
        self.view.on_close_tab(self._on_close_tab)
        self.view.on_tab_changed(self._on_tab_changed)
        self.view.on_find(self._on_find)
        self.view.on_replace(self._on_replace)
        self.view.on_macro_toggle(self._on_macro_toggle)
        self.view.on_macro_play(self._on_macro_play)
        self.view.on_buffer_type_change(self._on_buffer_type_changed)

    def _on_text_change(self) -> None:
        if self._syncing:
            return

        tab = self.active_tab
        if not tab:
            return

        old_text = tab.document.get_text()
        new_text = self.view.get_text()

        if old_text == new_text:
            return

        command = self._detect_change(tab.document.buffer, old_text, new_text)
        if command:
            tab.document.execute(command)
            tab.search_engine.invalidate_cache()
            self._update_status()
            self._update_tab_title()

    def _detect_change(
        self, buffer: TextBuffer, old_text: str, new_text: str
    ) -> Optional[Command]:
        len_old = len(old_text)
        len_new = len(new_text)

        start = 0
        while start < len_old and start < len_new and old_text[start] == new_text[start]:
            start += 1

        old_end = len_old
        new_end = len_new
        while old_end > start and new_end > start and old_text[old_end - 1] == new_text[new_end - 1]:
            old_end -= 1
            new_end -= 1

        deleted_len = old_end - start
        inserted_text = new_text[start:new_end]

        if deleted_len > 0 and inserted_text:
            return ReplaceCommand(buffer, start, deleted_len, inserted_text)
        elif deleted_len > 0:
            return DeleteCommand(buffer, start, deleted_len)
        elif inserted_text:
            return InsertCommand(buffer, start, inserted_text)

        return None

    def _on_undo(self) -> None:
        tab = self.active_tab
        if not tab or not tab.document.can_undo:
            return

        last_cmd = tab.document.undo_stack[-1]
        undo_cursor = last_cmd.undo_cursor_pos

        if tab.document.undo():
            self._sync_view_from_document()
            if undo_cursor is not None:
                self.view.set_cursor_position(undo_cursor)
            tab.search_engine.invalidate_cache()
            self._update_status()
            self._update_tab_title()

    def _on_redo(self) -> None:
        tab = self.active_tab
        if not tab or not tab.document.can_redo:
            return

        next_cmd = tab.document.redo_stack[-1]
        redo_cursor = next_cmd.cursor_pos

        if tab.document.redo():
            self._sync_view_from_document()
            if redo_cursor is not None:
                self.view.set_cursor_position(redo_cursor)
            tab.search_engine.invalidate_cache()
            self._update_status()
            self._update_tab_title()

    def _sync_view_from_document(self) -> None:
        tab = self.active_tab
        if not tab:
            return
        self._syncing = True
        try:
            self.view.set_text(tab.document.get_text())
        finally:
            self._syncing = False

    def _new_tab(self, title: str = "Untitled", content: str = "") -> None:
        buffer_cls = BUFFER_TYPES.get(self.current_buffer_key, PieceTable)
        doc = Document(buffer_type=buffer_cls)
        if content:
            doc.set_text(content)
            doc.mark_saved()

        tab = TabState(document=doc, title=title)
        self.tabs.append(tab)
        self.view.add_tab(title)

        self._sync_view_from_document()
        self._update_status()

    def _on_new(self) -> None:
        tab_num = len(self.tabs) + 1
        self._new_tab(title=f"Untitled-{tab_num}")

    def _on_open(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt *.py *.md *.json *.js *.html *.css"), ("All files", "*.*")]
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            base_name = os.path.basename(path)
            self._new_tab(title=base_name, content=content)
            self.tabs[-1].filepath = path
            self._update_status()
            self._update_tab_title()
        except Exception as e:
            messagebox.showerror("Error Opening File", str(e))

    def _on_save(self) -> None:
        tab = self.active_tab
        if not tab:
            return
        if not tab.filepath:
            self._on_save_as()
            return

        try:
            with open(tab.filepath, "w", encoding="utf-8") as f:
                f.write(tab.document.get_text())
            tab.document.mark_saved()
            self._update_status()
            self._update_tab_title()
        except Exception as e:
            messagebox.showerror("Error Saving File", str(e))

    def _on_save_as(self) -> None:
        tab = self.active_tab
        if not tab:
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt *.py *.md *.json"), ("All files", "*.*")]
        )
        if not path:
            return

        tab.filepath = path
        tab.title = os.path.basename(path)
        self._on_save()

    def _on_close_tab(self) -> None:
        idx = self.view.get_active_tab_index()
        if idx < 0 or idx >= len(self.tabs):
            return

        tab = self.tabs[idx]
        if tab.document.is_modified:
            resp = messagebox.askyesnocancel("Unsaved Changes", f"Save changes to {tab.title} before closing?")
            if resp is None:
                return
            if resp:
                self._on_save()

        self.view.close_tab(idx)
        self.tabs.pop(idx)

        if not self.tabs:
            self._new_tab()
        else:
            self._on_tab_changed()

    def _on_tab_changed(self) -> None:
        tab = self.active_tab
        if not tab:
            return
        self._sync_view_from_document()
        self._update_status()
        if self.search_dialog and self.search_dialog.winfo_exists():
            self._on_query_changed()

    def _update_tab_title(self) -> None:
        idx = self.view.get_active_tab_index()
        tab = self.active_tab
        if not tab or idx < 0:
            return
        marker = " *" if tab.document.is_modified else ""
        display_title = f"{tab.title}{marker}"
        self.view.set_tab_title(idx, display_title)
        self.root.title(f"{display_title} - Stack-Based Undo/Redo Text Editor")

    def _update_status(self) -> None:
        tab = self.active_tab
        if not tab:
            return
        text_w = self.view.get_active_text_widget()
        if text_w:
            line, col = text_w.index(tk.INSERT).split(".")
            self.view.update_status(
                int(line), int(col), tab.document.is_modified, self.current_buffer_key
            )
        self.view.update_history(tab.document.get_history())

    def _on_find(self) -> None:
        if self.search_dialog and self.search_dialog.winfo_exists():
            self.search_dialog.lift()
            return
        self.search_dialog = SearchDialog(self.root, mode="find")
        self._setup_search_dialog()

    def _on_replace(self) -> None:
        if self.search_dialog and self.search_dialog.winfo_exists():
            self.search_dialog.destroy()
        self.search_dialog = SearchDialog(self.root, mode="replace")
        self._setup_search_dialog()

    def _setup_search_dialog(self) -> None:
        self.search_dialog.on_find_next(self._on_find_next)
        self.search_dialog.on_find_prev(self._on_find_prev)
        self.search_dialog.on_replace_one(self._on_replace_one)
        self.search_dialog.on_replace_all(self._on_replace_all)
        self.search_dialog.on_query_changed(self._on_query_changed)
        self.search_dialog.on_close(self._on_search_dialog_closed)
        self._on_query_changed()

    def _on_query_changed(self) -> None:
        if not self.search_dialog or not self.search_dialog.winfo_exists():
            return
        tab = self.active_tab
        if not tab:
            return

        query = self.search_dialog.get_query()
        options = self.search_dialog.get_options()

        if not query:
            self.view.clear_highlights()
            self.search_dialog.clear_status()
            return

        text = tab.document.get_text()
        matches = tab.search_engine.find_all(text, query, options)
        self.view.highlight_matches(matches)

        if matches:
            self.search_dialog.set_match_info(tab.search_engine.current_match_index, len(matches))
        else:
            self.search_dialog.set_no_matches()

    def _on_find_next(self) -> None:
        if not self.search_dialog:
            return
        tab = self.active_tab
        if not tab:
            return

        query = self.search_dialog.get_query()
        options = self.search_dialog.get_options()
        cursor_pos = self.view.get_cursor_position()

        match = tab.search_engine.find_next(tab.document.get_text(), query, cursor_pos, options)
        if match:
            self.view.highlight_current_match(match)
            self.view.set_cursor_position(match.end)
            self.search_dialog.set_match_info(tab.search_engine.current_match_index, tab.search_engine.match_count)
        else:
            self.search_dialog.set_no_matches()

    def _on_find_prev(self) -> None:
        if not self.search_dialog:
            return
        tab = self.active_tab
        if not tab:
            return

        query = self.search_dialog.get_query()
        options = self.search_dialog.get_options()
        cursor_pos = self.view.get_cursor_position()

        match = tab.search_engine.find_previous(tab.document.get_text(), query, cursor_pos, options)
        if match:
            self.view.highlight_current_match(match)
            self.view.set_cursor_position(match.start)
            self.search_dialog.set_match_info(tab.search_engine.current_match_index, tab.search_engine.match_count)
        else:
            self.search_dialog.set_no_matches()

    def _on_replace_one(self) -> None:
        if not self.search_dialog:
            return
        tab = self.active_tab
        if not tab:
            return

        query = self.search_dialog.get_query()
        replacement = self.search_dialog.get_replacement()
        options = self.search_dialog.get_options()
        cursor_pos = self.view.get_cursor_position()

        match = tab.search_engine.find_next(tab.document.get_text(), query, cursor_pos, options)
        if match:
            cmd = tab.search_engine.replace_one(tab.document.buffer, match, replacement)
            tab.document.execute(cmd)
            self._sync_view_from_document()
            self._on_query_changed()
            self._update_status()
            self._update_tab_title()

    def _on_replace_all(self) -> None:
        if not self.search_dialog:
            return
        tab = self.active_tab
        if not tab:
            return

        query = self.search_dialog.get_query()
        replacement = self.search_dialog.get_replacement()
        options = self.search_dialog.get_options()

        cmd = tab.search_engine.replace_all(
            tab.document.buffer, tab.document.get_text(), query, replacement, options
        )
        if cmd:
            tab.document.execute(cmd)
            self._sync_view_from_document()
            self._on_query_changed()
            self._update_status()
            self._update_tab_title()

    def _on_search_dialog_closed(self) -> None:
        self.view.clear_highlights()
        self.search_dialog = None

    def _on_macro_toggle(self) -> None:
        tab = self.active_tab
        if not tab:
            return

        if tab.is_recording_macro:
            tab.macro_commands = tab.document.stop_macro_recording()
            tab.is_recording_macro = False
            self.view.update_macro_status(False)
        else:
            tab.document.start_macro_recording()
            tab.is_recording_macro = True
            self.view.update_macro_status(True)

    def _on_macro_play(self) -> None:
        tab = self.active_tab
        if not tab or not tab.macro_commands:
            return
        tab.document.replay_macro(tab.macro_commands)
        self._sync_view_from_document()
        self._update_status()
        self._update_tab_title()

    def _on_buffer_type_changed(self, buffer_key: str) -> None:
        self.current_buffer_key = buffer_key
        tab = self.active_tab
        if tab:
            buffer_cls = BUFFER_TYPES.get(buffer_key, PieceTable)
            current_text = tab.document.get_text()
            new_doc = Document(buffer_type=buffer_cls)
            if current_text:
                new_doc.set_text(current_text)
                if not tab.document.is_modified:
                    new_doc.mark_saved()
            tab.document = new_doc
            self._update_status()
