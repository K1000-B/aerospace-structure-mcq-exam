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
        self.bg_color = "#f8fafc"       # airy background
        self.card_color = "#ffffff"     # panels
        self.card_border = "#e2e8f0"    # soft outline
        self.accent_color = "#2563eb"   # primary blue
        self.accent_hover = "#1d4ed8"
        self.correct_color = "#16a34a"  # green
        self.wrong_color = "#dc2626"    # red
        self.text_color = "#0f172a"     # dark text
        self.muted_text = "#475569"     # secondary text

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
        self.bubbles = []

        # Load data + build UI
        self.load_questions(json_path)
        self.build_ui()
        self.animate_background()

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
        self.background_canvas = tk.Canvas(
            self,
            bg=self.bg_color,
            highlightthickness=0,
            bd=0,
        )
        self.background_canvas.place(x=0, y=0, relwidth=1, relheight=1)

        header = tk.Frame(self, bg=self.bg_color, bd=0)
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
        left_panel = tk.Frame(
            main,
            bg=self.card_color,
            bd=0,
            highlightthickness=1,
            highlightbackground=self.card_border,
        )
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
            bg="#eef2ff",
            fg=self.text_color,
            selectbackground=self.accent_color,
            selectforeground="#ffffff",
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
            fg="#ffffff",
            bd=0,
            font=("Helvetica", 11, "bold"),
            activebackground=self.accent_hover,
            activeforeground="#ffffff",
            padx=12,
            pady=8,
            relief="flat",
            cursor="hand2",
        )
        start_theme_btn.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 12))
        self._add_hover_effect(start_theme_btn, self.accent_color, self.accent_hover)

        # Right panel: quiz card
        quiz_card = tk.Frame(
            main,
            bg=self.card_color,
            bd=0,
            highlightthickness=1,
            highlightbackground=self.card_border,
        )
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
            bg=self.accent_color,
            fg="#ffffff",
            bd=0,
            font=("Helvetica", 11, "bold"),
            activebackground=self.accent_hover,
            activeforeground="#ffffff",
            padx=14,
            pady=8,
            relief="flat",
            state="disabled",
            cursor="hand2",
        )
        self.submit_btn.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self._add_hover_effect(self.submit_btn, self.accent_color, self.accent_hover)

        self.next_btn = tk.Button(
            bottom_bar,
            text="Next question",
            command=self.on_next,
            bg="#10b981",
            fg="#0b2b1f",
            bd=0,
            font=("Helvetica", 11, "bold"),
            activebackground="#0ea371",
            activeforeground="#0b2b1f",
            padx=14,
            pady=8,
            relief="flat",
            state="disabled",
            cursor="hand2",
        )
        self.next_btn.grid(row=0, column=2, sticky="e")
        self._add_hover_effect(self.next_btn, "#10b981", "#0ea371")

    def _add_hover_effect(self, widget: tk.Widget, normal_color: str, hover_color: str) -> None:
        def on_enter(_event: tk.Event) -> None:  # type: ignore[type-arg]
            widget.config(bg=hover_color)

        def on_leave(_event: tk.Event) -> None:  # type: ignore[type-arg]
            widget.config(bg=normal_color)

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def animate_background(self) -> None:
        """Create soft, floating shapes to make the experience dynamic yet minimal."""

        if not hasattr(self, "background_canvas"):
            return

        # Send the canvas behind other widgets without requiring a tag/id argument
        self.background_canvas.tk.call("lower", self.background_canvas._w)
        self.after(120, self._seed_bubbles)
        self.after(220, self._move_bubbles)

    def _seed_bubbles(self) -> None:
        if not hasattr(self, "background_canvas"):
            return

        self.background_canvas.delete("all")
        self.bubbles = []
        width = max(self.winfo_width(), 900)
        height = max(self.winfo_height(), 550)
        palette = ["#dbeafe", "#e0f2fe", "#e2e8f0", "#bfdbfe"]

        for _ in range(9):
            size = random.randint(60, 140)
            x = random.randint(-40, width - size + 40)
            y = random.randint(-40, height - size + 40)
            bubble = self.background_canvas.create_oval(
                x,
                y,
                x + size,
                y + size,
                fill=random.choice(palette),
                outline="",
                stipple="gray12",
            )
            self.bubbles.append(
                {
                    "id": bubble,
                    "dx": random.choice([-1, 1]) * random.uniform(0.3, 0.8),
                    "dy": random.choice([-1, 1]) * random.uniform(0.3, 0.8),
                }
            )

    def _move_bubbles(self) -> None:
        if not hasattr(self, "background_canvas") or not self.bubbles:
            self.after(300, self._move_bubbles)
            return

        width = max(self.winfo_width(), 900)
        height = max(self.winfo_height(), 550)

        for bubble in self.bubbles:
            item_id = bubble["id"]
            dx = bubble["dx"]
            dy = bubble["dy"]
            self.background_canvas.move(item_id, dx, dy)
            x1, y1, x2, y2 = self.background_canvas.coords(item_id)

            if x1 <= -60 or x2 >= width + 60:
                bubble["dx"] = -dx
            if y1 <= -60 or y2 >= height + 60:
                bubble["dy"] = -dy

        self.after(60, self._move_bubbles)

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
                    selectcolor="#e2e8f0",
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
                    selectcolor="#e2e8f0",
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
