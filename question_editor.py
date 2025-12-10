#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple GUI to add questions to the MMC questions JSON database."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import tkinter as tk
from tkinter import messagebox, ttk


QuestionCategory = str


class QuestionEditor(tk.Tk):
    """Collect new questions via a friendly form and append them to the JSON file."""

    def __init__(self, json_path: str = "mmc_questions.json") -> None:
        super().__init__()
        self.json_path = Path(json_path)
        self.title("MMC question editor")
        self.geometry("800x700")
        self.minsize(760, 620)

        self.questions: List[dict] = self._load_existing_questions()

        self.accent = "#2563eb"
        self.bg = "#f8fafc"
        self.card = "#ffffff"
        self.border = "#e2e8f0"
        self.text = "#0f172a"
        self.muted = "#000000"

        self.configure(bg=self.bg)

        self.category_var = tk.StringVar(value="TF")
        self.thematic_var = tk.StringVar()
        self.tf_answer_var = tk.BooleanVar(value=True)
        self.qcm_answer_var = tk.StringVar(value="")
        self.choice_entries: List[tk.Entry] = []

        self.status_var = tk.StringVar()

        self._build_layout()
        self._refresh_next_id_label()
        self._show_category_fields("TF")

    # ---------- Data helpers ----------
    def _load_existing_questions(self) -> List[dict]:
        if not self.json_path.exists():
            return []

        with self.json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict) and isinstance(data.get("questions"), list):
            return data["questions"]
        if isinstance(data, list):
            return data
        return []

    def _write_questions(self) -> None:
        payload = {"questions": self.questions}
        self.json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _next_id(self) -> int:
        if not self.questions:
            return 1
        return max(int(q.get("id", 0)) for q in self.questions) + 1

    # ---------- UI ----------
    def _build_layout(self) -> None:
        header = tk.Frame(self, bg=self.bg)
        header.pack(fill="x", padx=24, pady=(18, 12))

        title = tk.Label(
            header,
            text="Add a question to the MMC database",
            font=("Helvetica", 18, "bold"),
            fg=self.text,
            bg=self.bg,
        )
        title.grid(row=0, column=0, sticky="w")

        subtitle = tk.Label(
            header,
            text="Fill the form below and click Save. The file will be updated instantly.",
            font=("Helvetica", 11),
            fg=self.muted,
            bg=self.bg,
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(4, 0))

        stats = tk.Label(
            header,
            textvariable=self.status_var,
            font=("Helvetica", 10, "bold"),
            fg=self.accent,
            bg=self.bg,
        )
        stats.grid(row=2, column=0, sticky="w", pady=(6, 0))

        container = tk.Frame(
            self,
            bg=self.card,
            highlightbackground=self.border,
            highlightthickness=1,
            bd=0,
        )
        container.pack(fill="both", expand=True, padx=24, pady=(0, 22))

        container.columnconfigure(0, weight=1)

        # Category selection
        category_row = tk.Frame(container, bg=self.card)
        category_row.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))

        tk.Label(
            category_row,
            text="Category",
            font=("Helvetica", 12, "bold"),
            fg=self.text,
            bg=self.card,
        ).pack(side="left")

        option = ttk.Combobox(
            category_row,
            textvariable=self.category_var,
            values=["TF", "QCM"],
            state="readonly",
            width=6,
        )
        option.pack(side="left", padx=(12, 0))
        option.bind("<<ComboboxSelected>>", lambda _evt: self._show_category_fields(self.category_var.get()))

        self.next_id_label = tk.Label(
            category_row,
            text="",
            font=("Helvetica", 10),
            fg=self.muted,
            bg=self.card,
        )
        self.next_id_label.pack(side="right")

        # Thematic entry
        thematic_frame = tk.Frame(container, bg=self.card)
        thematic_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=8)
        thematic_frame.columnconfigure(1, weight=1)

        tk.Label(
            thematic_frame,
            text="Thematic",
            font=("Helvetica", 12, "bold"),
            fg=self.text,
            bg=self.card,
        ).grid(row=0, column=0, sticky="w", padx=(0, 10))

        tk.Entry(
            thematic_frame,
            textvariable=self.thematic_var,
            font=("Helvetica", 11),
        ).grid(row=0, column=1, sticky="ew")

        # Question body
        question_frame = tk.Frame(container, bg=self.card)
        question_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=8)
        question_frame.columnconfigure(0, weight=1)

        tk.Label(
            question_frame,
            text="Question",
            font=("Helvetica", 12, "bold"),
            fg=self.text,
            bg=self.card,
        ).grid(row=0, column=0, sticky="w")

        self.question_text = tk.Text(
            question_frame,
            height=7,
            wrap="word",
            font=("Helvetica", 11),
            highlightthickness=1,
            highlightbackground=self.border,
            relief="flat",
        )
        self.question_text.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.question_text.focus_set()

        # Frames that swap based on category
        self.tf_frame = tk.Frame(container, bg=self.card)
        self.qcm_frame = tk.Frame(container, bg=self.card)

        self._build_tf_frame()
        self._build_qcm_frame()

        # Action buttons
        actions = tk.Frame(container, bg=self.card)
        actions.grid(row=5, column=0, sticky="ew", padx=16, pady=(18, 14))
        actions.columnconfigure(0, weight=1)

        save_btn = tk.Button(
            actions,
            text="Save question",
            command=self._on_save,
            bg=self.accent,
            fg="black",
            bd=0,
            font=("Helvetica", 13, "bold"),
            padx=16,
            pady=12,
            activebackground="#1e40af",
            activeforeground="white",
            highlightthickness=0,
            cursor="hand2",
        )
        save_btn.grid(row=0, column=1, sticky="e")

    def _build_tf_frame(self) -> None:
        tk.Label(
            self.tf_frame,
            text="Answer",
            font=("Helvetica", 12, "bold"),
            fg=self.text,
            bg=self.card,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(10, 0))

        options = tk.Frame(self.tf_frame, bg=self.card)
        options.grid(row=1, column=0, sticky="w", padx=16, pady=(4, 10))

        tk.Radiobutton(
            options,
            text="True",
            variable=self.tf_answer_var,
            value=True,
            bg=self.card,
            font=("Helvetica", 11),
        ).pack(side="left")
        tk.Radiobutton(
            options,
            text="False",
            variable=self.tf_answer_var,
            value=False,
            bg=self.card,
            font=("Helvetica", 11),
        ).pack(side="left", padx=(12, 0))

    def _build_qcm_frame(self) -> None:
        tk.Label(
            self.qcm_frame,
            text="Choices",
            font=("Helvetica", 12, "bold"),
            fg=self.text,
            bg=self.card,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(10, 6))

        self.choices_container = tk.Frame(self.qcm_frame, bg=self.card)
        self.choices_container.grid(row=1, column=0, sticky="ew", padx=16)
        self.choices_container.columnconfigure(0, weight=1)

        tk.Button(
            self.qcm_frame,
            text="Add choice",
            command=self._add_choice_field,
            bg="#dbeafe",
            fg=self.accent,
            bd=0,
            font=("Helvetica", 11, "bold"),
            padx=12,
            pady=8,
            activebackground="#bfdbfe",
            activeforeground=self.accent,
            highlightthickness=0,
            cursor="hand2",
        ).grid(row=2, column=0, sticky="w", padx=16, pady=(8, 0))

        tk.Label(
            self.qcm_frame,
            text="Correct answer",
            font=("Helvetica", 12, "bold"),
            fg=self.text,
            bg=self.card,
        ).grid(row=3, column=0, sticky="w", padx=16, pady=(14, 0))

        self.answer_menu = ttk.Combobox(
            self.qcm_frame,
            textvariable=self.qcm_answer_var,
            state="readonly",
        )
        self.answer_menu.grid(row=4, column=0, sticky="ew", padx=16, pady=(4, 12))
        for _ in range(3):
            self._add_choice_field()
        self._refresh_answer_menu()

    def _add_choice_field(self, value: str = "") -> None:
        row = tk.Frame(self.choices_container, bg=self.card)
        row.grid(row=len(self.choice_entries), column=0, sticky="ew", pady=4)
        row.columnconfigure(0, weight=1)

        entry = tk.Entry(row, font=("Helvetica", 11))
        entry.insert(0, value)
        entry.grid(row=0, column=0, sticky="ew")
        entry.bind("<KeyRelease>", lambda _evt: self._refresh_answer_menu())
        self.choice_entries.append(entry)

        remove_btn = tk.Button(
            row,
            text="✕",
            command=lambda e=entry, r=row: self._remove_choice_field(e, r),
            bg="#fee2e2",
            fg="#7f1d1d",
            bd=0,
            font=("Helvetica", 11, "bold"),
            width=3,
            activebackground="#fecdd3",
            activeforeground="#7f1d1d",
            highlightthickness=0,
            cursor="hand2",
        )
        remove_btn.grid(row=0, column=1, padx=(6, 0))
        self._refresh_answer_menu()

    def _remove_choice_field(self, entry: tk.Entry, row: tk.Frame) -> None:
        entry.destroy()
        row.destroy()
        self.choice_entries.remove(entry)
        self._refresh_answer_menu()

    def _refresh_answer_menu(self) -> None:
        previous = self.qcm_answer_var.get()
        choices = [c.get().strip() for c in self.choice_entries if c.get().strip()]
        self.answer_menu["values"] = choices
        if previous in choices:
            self.qcm_answer_var.set(previous)
        elif choices:
            self.qcm_answer_var.set(choices[0])
        else:
            self.qcm_answer_var.set("")

    def _show_category_fields(self, category: QuestionCategory) -> None:
        self.tf_frame.grid_forget()
        self.qcm_frame.grid_forget()

        if category == "TF":
            self.tf_frame.grid(row=3, column=0, sticky="w", padx=0, pady=(2, 0))
        else:
            self.qcm_frame.grid(row=3, column=0, sticky="ew", padx=0, pady=(2, 0))
            self._refresh_answer_menu()

    def _refresh_next_id_label(self) -> None:
        total = len(self.questions)
        self.status_var.set(f"{total} question(s) currently in the database")
        self.next_id_label.config(text=f"Next id: {self._next_id()}")

    # ---------- Save flow ----------
    def _on_save(self) -> None:
        category = self.category_var.get()
        thematic = self.thematic_var.get().strip()
        question = self.question_text.get("1.0", "end").strip()

        if not thematic or not question:
            messagebox.showerror("Missing data", "Thematic and question text are required.")
            return

        if category == "TF":
            new_question = {
                "id": self._next_id(),
                "category": "TF",
                "thematic": thematic,
                "question": question,
                "choices": None,
                "answer": bool(self.tf_answer_var.get()),
            }
        else:
            choices = [c.get().strip() for c in self.choice_entries if c.get().strip()]
            if len(choices) < 2:
                messagebox.showerror("Not enough choices", "Provide at least two answer choices for a QCM question.")
                return

            answer = self.qcm_answer_var.get()
            if answer not in choices:
                messagebox.showerror("Invalid answer", "Select the correct answer from the choices list.")
                return

            new_question = {
                "id": self._next_id(),
                "category": "QCM",
                "thematic": thematic,
                "question": question,
                "choices": choices,
                "answer": answer,
            }

        self.questions.append(new_question)
        self._write_questions()

        messagebox.showinfo("Saved", f"Question {new_question['id']} added to {self.json_path}.")
        self._reset_form()
        self._refresh_next_id_label()

    def _reset_form(self) -> None:
        self.thematic_var.set("")
        self.question_text.delete("1.0", "end")
        self.category_var.set("TF")
        self.tf_answer_var.set(True)

        for entry in list(self.choice_entries):
            self._remove_choice_field(entry, entry.master)  # type: ignore[arg-type]
        for _ in range(3):
            self._add_choice_field()
        self.qcm_answer_var.set("")
        self._refresh_answer_menu()

        self._show_category_fields("TF")
        self.question_text.focus_set()


if __name__ == "__main__":
    app = QuestionEditor()
    app.mainloop()
