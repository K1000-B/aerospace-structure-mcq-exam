#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 10 15:38:57 2025

@author: camile
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import List, Optional, Union, Literal

import tkinter as tk
from tkinter import messagebox


# ---------- Data model ----------

QuestionCategory = Literal["TF", "QCM"]


@dataclass
class Question:
    id: int
    category: QuestionCategory
    thematic: str
    question: str

    # Only for QCM (None for TF)
    choices: Optional[List[str]]

    # bool for TF, str for QCM
    answer: Union[bool, str]


# ---------- Quiz application ----------

class QuizApp(tk.Tk):
    def __init__(self, json_path: str = "mmc_questions.json"):
        super().__init__()
        self.title("MMC QCM Trainer")
        self.geometry("1000x650")
        self.minsize(900, 550)

        # Design palette
        self.bg_color = "#0f172a"       # dark background
        self.card_color = "#111827"     # panels
        self.accent_color = "#38bdf8"   # cyan
        self.correct_color = "#22c55e"  # green
        self.wrong_color = "#ef4444"    # red
        self.text_color = "#e5e7eb"     # light text
        self.muted_text = "#9ca3af"     # secondary text

        self.configure(bg=self.bg_color)

        # State
        self.questions: List[Question] = []
        self.themes: List[str] = []
        self.current_theme: Optional[str] = None
        self.filtered_questions: List[Question] = []
        self.current_index: int = 0
        self.selected_var = tk.IntVar(value=-1)
        self.score: int = 0
        self.total: int = 0

        # Load data + build UI
        self.load_questions(json_path)
        self.build_ui()

    # ---------- Data loading ----------

    def load_questions(self, json_path: str) -> None:
        """Load questions from JSON (root key 'questions') into dataclasses."""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            if not isinstance(raw, dict) or "questions" not in raw:
                raise ValueError("JSON root must be an object with key 'questions'.")

            raw_list = raw["questions"]
            if not isinstance(raw_list, list):
                raise ValueError("'questions' must be a list.")

            self.questions = []
            for item in raw_list:
                # Basic validation + safe defaults
                q = Question(
                    id=int(item["id"]),
                    category=item["category"],
                    thematic=item["thematic"],
                    question=item["question"],
                    choices=item.get("choices"),
                    answer=item["answer"],
                )
                self.questions.append(q)

            # Unique thematics
            self.themes = sorted({q.thematic for q in self.questions})

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load questions:\n{e}")
            self.destroy()

    # ---------- UI building ----------

    def build_ui(self) -> None:
        """Build global layout."""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Header
        header = tk.Frame(self, bg=self.bg_color)
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 10))
        header.columnconfigure(0, weight=1)

        title_label = tk.Label(
            header,
            text="MMC Multiple-Choice Trainer",
            font=("Helvetica", 22, "bold"),
            fg=self.text_color,
            bg=self.bg_color,
        )
        title_label.grid(row=0, column=0, sticky="w")

        subtitle_label = tk.Label(
            header,
            text="Select a thematic, then answer MMC-style true/false and multiple-choice questions.",
            font=("Helvetica", 11),
            fg=self.muted_text,
            bg=self.bg_color,
        )
        subtitle_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

        # Main area (left: themes, right: quiz card)
        main = tk.Frame(self, bg=self.bg_color)
        main.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 20))
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=3)
        main.rowconfigure(0, weight=1)

        # Left panel: thematics list
        left_panel = tk.Frame(main, bg=self.card_color, bd=0, highlightthickness=0)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(1, weight=1)

        left_title = tk.Label(
            left_panel,
            text="Thematics",
            font=("Helvetica", 14, "bold"),
            fg=self.text_color,
            bg=self.card_color,
        )
        left_title.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        self.theme_listbox = tk.Listbox(
            left_panel,
            bg="#020617",
            fg=self.text_color,
            selectbackground=self.accent_color,
            selectforeground="#020617",
            activestyle="none",
            highlightthickness=0,
            bd=0,
            font=("Helvetica", 11),
        )
        self.theme_listbox.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 8))

        for t in self.themes:
            self.theme_listbox.insert(tk.END, t)

        start_theme_btn = tk.Button(
            left_panel,
            text="Start selected theme",
            command=self.on_start_theme,
            bg=self.accent_color,
            fg="#020617",
            bd=0,
            font=("Helvetica", 11, "bold"),
            activebackground="#0ea5e9",
            activeforeground="#020617",
            padx=10,
            pady=6,
        )
        start_theme_btn.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 12))

        # Right panel: quiz card
        quiz_card = tk.Frame(main, bg=self.card_color, bd=0, highlightthickness=0)
        quiz_card.grid(row=0, column=1, sticky="nsew")
        quiz_card.columnconfigure(0, weight=1)
        quiz_card.rowconfigure(2, weight=1)

        # Top info: thematic + category + score
        top_info = tk.Frame(quiz_card, bg=self.card_color)
        top_info.grid(row=0, column=0, sticky="ew", padx=24, pady=(18, 4))
        top_info.columnconfigure(0, weight=1)
        top_info.columnconfigure(1, weight=0)
        top_info.columnconfigure(2, weight=0)

        self.current_theme_label = tk.Label(
            top_info,
            text="No thematic selected",
            font=("Helvetica", 12, "bold"),
            fg=self.accent_color,
            bg=self.card_color,
        )
        self.current_theme_label.grid(row=0, column=0, sticky="w")

        self.category_label = tk.Label(
            top_info,
            text="Category: –",
            font=("Helvetica", 11),
            fg=self.muted_text,
            bg=self.card_color,
        )
        self.category_label.grid(row=0, column=1, sticky="e", padx=(0, 12))

        self.score_label = tk.Label(
            top_info,
            text="Score: 0 / 0",
            font=("Helvetica", 11),
            fg=self.muted_text,
            bg=self.card_color,
        )
        self.score_label.grid(row=0, column=2, sticky="e")

        # Question label
        self.question_label = tk.Label(
            quiz_card,
            text="Choose a thematic on the left and click “Start selected theme” to begin.",
            wraplength=650,
            justify="left",
            font=("Helvetica", 13),
            fg=self.text_color,
            bg=self.card_color,
        )
        self.question_label.grid(row=1, column=0, sticky="ew", padx=24, pady=(6, 10))

        # Answers area
        self.answers_frame = tk.Frame(quiz_card, bg=self.card_color)
        self.answers_frame.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 10))
        self.answers_frame.columnconfigure(0, weight=1)

        # Bottom bar: feedback + buttons
        bottom_bar = tk.Frame(quiz_card, bg=self.card_color)
        bottom_bar.grid(row=3, column=0, sticky="ew", padx=24, pady=(4, 16))
        bottom_bar.columnconfigure(0, weight=1)
        bottom_bar.columnconfigure(1, weight=0)
        bottom_bar.columnconfigure(2, weight=0)

        self.feedback_label = tk.Label(
            bottom_bar,
            text="",
            font=("Helvetica", 11, "bold"),
            fg=self.text_color,
            bg=self.card_color,
        )
        self.feedback_label.grid(row=0, column=0, sticky="w")

        self.submit_btn = tk.Button(
            bottom_bar,
            text="Submit answer",
            command=self.on_submit,
            bg="#1d4ed8",
            fg="white",
            bd=0,
            font=("Helvetica", 11, "bold"),
            activebackground="#1e40af",
            activeforeground="white",
            padx=14,
            pady=6,
            state="disabled",
        )
        self.submit_btn.grid(row=0, column=1, sticky="e", padx=(0, 8))

        self.next_btn = tk.Button(
            bottom_bar,
            text="Next question",
            command=self.on_next,
            bg="#0f766e",
            fg="white",
            bd=0,
            font=("Helvetica", 11, "bold"),
            activebackground="#115e59",
            activeforeground="white",
            padx=14,
            pady=6,
            state="disabled",
        )
        self.next_btn.grid(row=0, column=2, sticky="e")

    # ---------- Theme & navigation ----------

    def on_start_theme(self) -> None:
        """Start quiz for the selected thematic."""
        selection = self.theme_listbox.curselection()
        if not selection:
            messagebox.showinfo("Thematic", "Please select a thematic first.")
            return

        idx = selection[0]
        theme = self.themes[idx]
        self.start_theme(theme)

    def start_theme(self, theme: str) -> None:
        """Initialize quiz state for a given thematic."""
        self.current_theme = theme
        self.current_theme_label.config(text=f"Thematic: {theme}")

        self.filtered_questions = [q for q in self.questions if q.thematic == theme]
        if not self.filtered_questions:
            messagebox.showwarning("No questions", f"No questions found for '{theme}'.")
            return

        random.shuffle(self.filtered_questions)
        self.current_index = 0
        self.score = 0
        self.total = 0
        self.update_score_label()
        self.show_question()
        self.feedback_label.config(text="")
        self.submit_btn.config(state="normal")
        self.next_btn.config(state="disabled")

    def show_question(self) -> None:
        """Display current question and build answer widgets based on category."""
        if not self.filtered_questions:
            return

        if self.current_index >= len(self.filtered_questions):
            random.shuffle(self.filtered_questions)
            self.current_index = 0

        q = self.filtered_questions[self.current_index]

        self.question_label.config(
            text=f"Q{self.current_index + 1}: {q.question}"
        )
        self.category_label.config(text=f"Category: {q.category}")

        # Clear previous answers
        for child in self.answers_frame.winfo_children():
            child.destroy()

        self.selected_var.set(-1)

        if q.category == "TF":
            # True/False
            tf_choices = ["True", "False"]
            for idx, label in enumerate(tf_choices):
                rb = tk.Radiobutton(
                    self.answers_frame,
                    text=label,
                    variable=self.selected_var,
                    value=idx,
                    anchor="w",
                    justify="left",
                    wraplength=650,
                    bg=self.card_color,
                    fg=self.text_color,
                    activebackground=self.card_color,
                    activeforeground=self.text_color,
                    selectcolor="#020617",
                    font=("Helvetica", 12),
                    pady=4,
                )
                rb.grid(row=idx, column=0, sticky="ew", pady=2)
        else:
            # QCM
            choices = q.choices or []
            for idx, choice in enumerate(choices):
                rb = tk.Radiobutton(
                    self.answers_frame,
                    text=choice,
                    variable=self.selected_var,
                    value=idx,
                    anchor="w",
                    justify="left",
                    wraplength=650,
                    bg=self.card_color,
                    fg=self.text_color,
                    activebackground=self.card_color,
                    activeforeground=self.text_color,
                    selectcolor="#020617",
                    font=("Helvetica", 12),
                    pady=4,
                )
                rb.grid(row=idx, column=0, sticky="ew", pady=2)

        self.feedback_label.config(text="")
        self.submit_btn.config(state="normal")
        self.next_btn.config(state="disabled")

    # ---------- Answer checking ----------

    def on_submit(self) -> None:
        """Check the selected answer against the Question dataclass."""
        if not self.filtered_questions:
            return

        selection = self.selected_var.get()
        if selection < 0:
            messagebox.showinfo("Answer", "Please select an answer first.")
            return

        q = self.filtered_questions[self.current_index]

        self.total += 1

        if q.category == "TF":
            # index 0 → True, index 1 → False
            user_answer = (selection == 0)
            correct = bool(q.answer)  # type: ignore[arg-type]

            if user_answer == correct:
                self.score += 1
                self.feedback_label.config(
                    text="Correct ✅ (True/False question)",
                    fg=self.correct_color,
                )
            else:
                correct_str = "True" if correct else "False"
                self.feedback_label.config(
                    text=f"Incorrect ❌  |  Correct answer: {correct_str}",
                    fg=self.wrong_color,
                )
        else:
            # QCM: q.answer is the correct choice string
            choices = q.choices or []
            correct_str = str(q.answer)  # type: ignore[arg-type]

            try:
                correct_index = choices.index(correct_str)
            except ValueError:
                correct_index = -1

            if selection == correct_index:
                self.score += 1
                self.feedback_label.config(
                    text="Correct ✅",
                    fg=self.correct_color,
                )
            else:
                if 0 <= correct_index < len(choices):
                    correct_text = choices[correct_index]
                else:
                    correct_text = correct_str or "N/A"
                self.feedback_label.config(
                    text=f"Incorrect ❌  |  Correct answer: {correct_text}",
                    fg=self.wrong_color,
                )

        self.update_score_label()
        self.submit_btn.config(state="disabled")
        self.next_btn.config(state="normal")

    def on_next(self) -> None:
        """Go to next question in current thematic."""
        if not self.filtered_questions:
            return
        self.current_index += 1
        self.show_question()

    def update_score_label(self) -> None:
        """Update score display."""
        self.score_label.config(text=f"Score: {self.score} / {self.total}")


def main() -> None:
    app = QuizApp("mmc_questions.json")
    app.mainloop()


if __name__ == "__main__":
    main()
