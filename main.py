
import tkinter as tk
from tkinter import filedialog, messagebox


class TextEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Stack-Based Undo/Redo Text Editor")
        self.root.geometry("800x550")

        self.undo_stack = []
        self.redo_stack = []
        self.history = []

        self.current_text = ""
        self.updating = False

        toolbar = tk.Frame(root, padx=8, pady=8)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Undo", command=self.undo).pack(
            side="left", padx=4
        )
        tk.Button(toolbar, text="Redo", command=self.redo).pack(
            side="left", padx=4
        )
        tk.Button(toolbar, text="Clear", command=self.clear).pack(
            side="left", padx=4
        )
        tk.Button(toolbar, text="Open", command=self.open_file).pack(
            side="right", padx=4
        )
        tk.Button(toolbar, text="Save", command=self.save_file).pack(
            side="right", padx=4
        )

        self.editor = tk.Text(root, wrap="word", font=("Arial", 12))
        self.editor.pack(fill="both", expand=True, padx=10, pady=5)

        history_frame = tk.LabelFrame(
            root, text="Edit History", padx=8, pady=5
        )
        history_frame.pack(fill="x", padx=10, pady=8)

        self.history_list = tk.Listbox(history_frame, height=4)
        self.history_list.pack(fill="x")

        self.editor.bind("<KeyRelease>", self.record_change)
        self.editor.bind(
            "<<Paste>>",
            lambda event: root.after(50, self.record_change)
        )
        self.editor.bind(
            "<<Cut>>",
            lambda event: root.after(50, self.record_change)
        )

        root.bind("<Control-z>", lambda event: self.undo())
        root.bind("<Control-y>", lambda event: self.redo())
        root.bind("<Control-s>", lambda event: self.save_file())
        root.bind("<Control-o>", lambda event: self.open_file())

        self.add_history("Editor opened")

    def get_text(self):
        return self.editor.get("1.0", "end-1c")

    def set_text(self, text):
        self.updating = True
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", text)
        self.updating = False

    def add_history(self, action):
        self.history.append(action)
        self.history_list.delete(0, "end")

        for item in reversed(self.history[-20:]):
            self.history_list.insert("end", item)

    def record_change(self, event=None):
        if self.updating:
            return

        new_text = self.get_text()

        if new_text != self.current_text:
            self.undo_stack.append(self.current_text)
            self.redo_stack.clear()
            self.current_text = new_text
            self.add_history("Text edited")

    def undo(self):
        if not self.undo_stack:
            return

        self.redo_stack.append(self.current_text)
        self.current_text = self.undo_stack.pop()
        self.set_text(self.current_text)
        self.add_history("Undo")

    def redo(self):
        if not self.redo_stack:
            return

        self.undo_stack.append(self.current_text)
        self.current_text = self.redo_stack.pop()
        self.set_text(self.current_text)
        self.add_history("Redo")

    def clear(self):
        if not self.get_text():
            return

        self.record_change()
        self.undo_stack.append(self.current_text)
        self.current_text = ""
        self.redo_stack.clear()
        self.set_text("")
        self.add_history("Document cleared")

    def save_file(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")]
        )

        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as file:
                file.write(self.get_text())

            self.add_history("File saved")
            messagebox.showinfo("Saved", "File saved successfully!")
        except OSError as error:
            messagebox.showerror("Error", str(error))

    def open_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt")]
        )

        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as file:
                text = file.read()

            self.undo_stack.append(self.current_text)
            self.redo_stack.clear()
            self.current_text = text
            self.set_text(text)
            self.add_history("File opened")
        except OSError as error:
            messagebox.showerror("Error", str(error))


if __name__ == "__main__":
    root = tk.Tk()
    app = TextEditor(root)
    root.mainloop()

