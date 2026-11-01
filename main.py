import tkinter as tk
from controllers.editor_controller import EditorController


def main() -> None:
    root = tk.Tk()
    root.title("Stack-Based Undo/Redo Text Editor")
    root.geometry("1050x700")

    app = EditorController(root)
    root.mainloop()


if __name__ == "__main__":
    main()
