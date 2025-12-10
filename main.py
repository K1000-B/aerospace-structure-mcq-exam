#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 10 15:38:57 2025

@author: camile
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Literal

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


# ---------- Persistent stats manager ----------


class StatsManager:
    def __init__(self, storage_path: Path):
        self.storage_path = Path(storage_path)
        self.data: Dict[str, Any] = {
            "attempts": [],
            "goal": {"target": None, "label": ""},
        }
        self.load()

    def load(self) -> None:
        if self.storage_path.exists():
            with self.storage_path.open("r", encoding="utf-8") as f:
                try:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        self.data.update(saved)
                except json.JSONDecodeError:
                    # Corrupted file: reset to defaults
                    self.data = {
                        "attempts": [],
                        "goal": {"target": None, "label": ""},
                    }

    def save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self.storage_path.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def record_attempt(
        self,
        question: Question,
        correct: bool,
        source: str,
        timestamp: Optional[float] = None,
    ) -> None:
        payload = {
            "question_id": question.id,
            "theme": question.thematic,
            "category": question.category,
            "correct": bool(correct),
            "source": source,
            "ts": timestamp if timestamp is not None else time.time(),
        }
        self.data.setdefault("attempts", []).append(payload)
        self.save()

    def set_goal(self, target_percent: float, label: str = "") -> None:
        self.data["goal"] = {"target": float(target_percent), "label": label}
        self.save()

    def get_goal(self) -> Dict[str, Any]:
        return self.data.get("goal", {"target": None, "label": ""})

    def _filtered_attempts(self, theme: Optional[str] = None) -> List[Dict[str, Any]]:
        attempts = self.data.get("attempts", [])
        if theme is None or theme == "Tous":
            return attempts
        return [a for a in attempts if a.get("theme") == theme]

    def compute_overall(self, theme: Optional[str] = None) -> Dict[str, Any]:
        attempts = self._filtered_attempts(theme)
        total = len(attempts)
        correct = sum(1 for a in attempts if a.get("correct"))
        rate = (correct / total) * 100 if total else 0.0
        return {"total": total, "correct": correct, "rate": rate}

    def theme_breakdown(self, *, theme: Optional[str] = None) -> Dict[str, Dict[str, float]]:
        attempts = self._filtered_attempts(theme)
        results: Dict[str, Dict[str, float]] = {}
        for attempt in attempts:
            theme = attempt.get("theme", "Unknown")
            results.setdefault(theme, {"total": 0, "correct": 0})
            results[theme]["total"] += 1
            if attempt.get("correct"):
                results[theme]["correct"] += 1

        for theme, res in results.items():
            total = res.get("total", 0)
            correct = res.get("correct", 0)
            res["rate"] = (correct / total) * 100 if total else 0.0
        return results

    def progress_speed(self, window: int = 10) -> Optional[float]:
        attempts = self.data.get("attempts", [])
        if len(attempts) < window * 2:
            return None

        recent = attempts[-window:]
        previous = attempts[-window * 2 : -window]
        recent_rate = (
            sum(1 for a in recent if a.get("correct")) / window * 100
        )
        previous_rate = (
            sum(1 for a in previous if a.get("correct")) / window * 100
        )
        return recent_rate - previous_rate

    def moving_success(self, window: int = 5, theme: Optional[str] = None) -> List[tuple[int, float]]:
        attempts = sorted(
            self._filtered_attempts(theme), key=lambda a: a.get("ts", 0)
        )
        if not attempts:
            return []

        rolling: List[int] = []
        points: List[tuple[int, float]] = []
        for idx, attempt in enumerate(attempts, start=1):
            rolling.append(1 if attempt.get("correct") else 0)
            if len(rolling) > window:
                rolling.pop(0)
            rate = (sum(rolling) / len(rolling)) * 100
            points.append((idx, rate))
        return points


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
        self.exam_mode: bool = False
        self.exam_user_answers: List[Optional[Union[bool, str]]] = []
        self.timer_running: bool = False
        self.timer_start: float = 0.0
        self.stats = StatsManager(Path(__file__).with_name("progress_data.json"))

        # Load data + build UI
        self.load_questions(json_path)
        self.build_ui()
        self.update_progress_card()
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
            fg="black",
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

        exam_btn = tk.Button(
            left_panel,
            text="Start exam (3 TF + 3 QCM)",
            command=self.start_exam_mode,
            bg="#0ea5e9",
            fg="#0b2b1f",
            bd=0,
            font=("Helvetica", 11, "bold"),
            activebackground="#0284c7",
            activeforeground="#0b2b1f",
            padx=12,
            pady=8,
            relief="flat",
            cursor="hand2",
        )
        exam_btn.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 16))
        self._add_hover_effect(exam_btn, "#0ea5e9", "#0284c7")

        progress_card = tk.Frame(
            left_panel,
            bg="#eef2ff",
            bd=0,
            highlightthickness=1,
            highlightbackground=self.card_border,
        )
        progress_card.grid(row=4, column=0, sticky="nsew", padx=16, pady=(0, 16))
        progress_card.columnconfigure(0, weight=1)

        progress_title = tk.Label(
            progress_card,
            text="Suivi & objectifs",
            font=("Helvetica", 13, "bold"),
            fg=self.text_color,
            bg="#eef2ff",
        )
        progress_title.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

        self.overall_progress_label = tk.Label(
            progress_card,
            text="Taux de réussite : –",
            font=("Helvetica", 11),
            fg=self.text_color,
            bg="#eef2ff",
            wraplength=200,
            justify="left",
        )
        self.overall_progress_label.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 4))

        self.goal_status_label = tk.Label(
            progress_card,
            text="Objectif : non défini",
            font=("Helvetica", 11),
            fg=self.muted_text,
            bg="#eef2ff",
            wraplength=200,
            justify="left",
        )
        self.goal_status_label.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 8))

        stats_btn = tk.Button(
            progress_card,
            text="Voir le suivi détaillé",
            command=self.show_stats_window,
            bg=self.accent_color,
            fg="white",
            bd=0,
            font=("Helvetica", 11, "bold"),
            activebackground=self.accent_hover,
            activeforeground="white",
            padx=10,
            pady=6,
            relief="flat",
            cursor="hand2",
        )
        stats_btn.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
        self._add_hover_effect(stats_btn, self.accent_color, self.accent_hover)

        dashboard_btn = tk.Button(
            progress_card,
            text="Ouvrir le dashboard",
            command=self.show_dashboard,
            bg="#0ea5e9",
            fg="#0b2b1f",
            bd=0,
            font=("Helvetica", 11, "bold"),
            activebackground="#0284c7",
            activeforeground="#0b2b1f",
            padx=10,
            pady=6,
            relief="flat",
            cursor="hand2",
        )
        dashboard_btn.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 14))
        self._add_hover_effect(dashboard_btn, "#0ea5e9", "#0284c7")

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
        top_info.columnconfigure(3, weight=0)

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

        self.timer_label = tk.Label(
            top_info,
            text="Timer: 00:00",
            font=("Helvetica", 11),
            fg=self.muted_text,
            bg=self.card_color,
        )
        self.timer_label.grid(row=0, column=3, sticky="e", padx=(12, 0))

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
            fg="black",
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
            fg="#000000",
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

    # ---------- Progress tracking ----------

    def update_progress_card(self) -> None:
        overall = self.stats.compute_overall()
        goal = self.stats.get_goal()
        rate_text = "Taux de réussite : –"
        if overall["total"]:
            rate_text = (
                f"Taux de réussite : {overall['rate']:.1f}%"
                f" ({overall['correct']}/{overall['total']})"
            )
        self.overall_progress_label.config(text=rate_text)

        goal_target = goal.get("target")
        if goal_target is None:
            goal_text = "Objectif : non défini"
        else:
            delta = goal_target - overall.get("rate", 0)
            if delta <= 0:
                goal_text = f"Objectif atteint ({goal_target:.1f}%). Bravo !"
            else:
                goal_text = f"Objectif : {goal_target:.1f}% (encore {delta:.1f} pts)"

            label = goal.get("label") or ""
            if label:
                goal_text += f"\n“{label}”"

        self.goal_status_label.config(text=goal_text)

    def _render_theme_stats(self) -> str:
        breakdown = self.stats.theme_breakdown()
        if not breakdown:
            return "Aucune tentative enregistrée."

        lines = ["Performance par thématique :"]
        for theme, stats in sorted(breakdown.items()):
            lines.append(
                f"- {theme} : {stats.get('rate', 0):.1f}%"
                f" ({int(stats.get('correct', 0))}/{int(stats.get('total', 0))})"
            )
        return "\n".join(lines)

    def show_stats_window(self) -> None:
        win = tk.Toplevel(self)
        win.title("Suivi des performances")
        win.geometry("520x520")

        overall = self.stats.compute_overall()
        progress_delta = self.stats.progress_speed()
        goal = self.stats.get_goal()

        header = tk.Label(
            win,
            text="Suivi détaillé",
            font=("Helvetica", 14, "bold"),
        )
        header.pack(pady=(12, 6))

        if not overall["total"]:
            summary_text = "Pas encore de données. Répondez à quelques questions pour activer le suivi."
        else:
            delta_text = (
                f"{progress_delta:+.1f} points" if progress_delta is not None else "N/A"
            )
            summary_text = (
                f"Taux de réussite global : {overall['rate']:.1f}%"
                f" ({overall['correct']}/{overall['total']})\n"
                f"Vitesse de progression (derniers 10 vs précédents) : {delta_text}"
            )
        summary_label = tk.Label(
            win,
            text=summary_text,
            justify="left",
            wraplength=480,
        )
        summary_label.pack(padx=12, pady=(0, 10), anchor="w")

        theme_stats = tk.Label(
            win,
            text=self._render_theme_stats(),
            justify="left",
            wraplength=480,
            anchor="w",
        )
        theme_stats.pack(padx=12, pady=(0, 10), anchor="w")

        goal_frame = tk.LabelFrame(win, text="Objectif", padx=10, pady=8)
        goal_frame.pack(fill="x", padx=12, pady=6)

        tk.Label(goal_frame, text="Taux cible (%) :").grid(row=0, column=0, sticky="w")
        goal_entry = tk.Entry(goal_frame)
        goal_entry.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        tk.Label(goal_frame, text="Nom de l'objectif (optionnel) :").grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )
        label_entry = tk.Entry(goal_frame)
        label_entry.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))
        goal_frame.columnconfigure(1, weight=1)

        if goal.get("target") is not None:
            goal_entry.insert(0, f"{goal['target']:.1f}")
        if goal.get("label"):
            label_entry.insert(0, goal["label"])

        feedback_label = tk.Label(goal_frame, text="", fg=self.correct_color)
        feedback_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        def save_goal() -> None:
            try:
                target = float(goal_entry.get())
                self.stats.set_goal(target, label_entry.get().strip())
                feedback_label.config(text="Objectif enregistré.", fg=self.correct_color)
                self.update_progress_card()
            except ValueError:
                feedback_label.config(
                    text="Veuillez saisir un pourcentage valide.", fg=self.wrong_color
                )

        save_btn = tk.Button(
            goal_frame,
            text="Enregistrer l'objectif",
            command=save_goal,
            bg=self.accent_color,
            fg="white",
            bd=0,
            font=("Helvetica", 10, "bold"),
            activebackground=self.accent_hover,
            activeforeground="white",
            padx=8,
            pady=6,
            relief="flat",
        )
        save_btn.grid(row=3, column=0, columnspan=2, sticky="e", pady=(8, 0))

    def show_dashboard(self) -> None:
        if hasattr(self, "dashboard_win") and self.dashboard_win.winfo_exists():
            self.dashboard_win.focus_set()
            self.refresh_dashboard()
            return

        win = tk.Toplevel(self)
        self.dashboard_win = win
        win.title("Dashboard interactif")
        win.geometry("1020x720")
        win.configure(bg=self.bg_color)

        header = tk.Frame(win, bg=self.bg_color)
        header.pack(fill="x", padx=18, pady=(16, 8))

        tk.Label(
            header,
            text="Dashboard de progression",
            font=("Helvetica", 18, "bold"),
            fg=self.text_color,
            bg=self.bg_color,
        ).grid(row=0, column=0, sticky="w")

        tk.Label(
            header,
            text="Visualisez vos performances globales, par thème et dans le temps. Filtrez les données pour explorer votre progression.",
            font=("Helvetica", 11),
            fg=self.muted_text,
            bg=self.bg_color,
            wraplength=760,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

        controls = tk.Frame(win, bg=self.bg_color)
        controls.pack(fill="x", padx=18, pady=(6, 12))

        tk.Label(
            controls, text="Filtrer par thématique :", bg=self.bg_color, fg=self.text_color
        ).grid(row=0, column=0, sticky="w")

        theme_choices = ["Tous"] + self.themes
        self.dashboard_theme_var = tk.StringVar(value="Tous")
        theme_menu = tk.OptionMenu(
            controls, self.dashboard_theme_var, *theme_choices, command=lambda _v: self.refresh_dashboard()
        )
        theme_menu.config(bg="#e0f2fe", fg=self.text_color, bd=0, highlightthickness=0)
        theme_menu.grid(row=0, column=1, sticky="w", padx=(8, 16))

        refresh_btn = tk.Button(
            controls,
            text="Actualiser",
            command=self.refresh_dashboard,
            bg=self.accent_color,
            fg="white",
            bd=0,
            font=("Helvetica", 10, "bold"),
            activebackground=self.accent_hover,
            activeforeground="white",
            padx=8,
            pady=6,
            relief="flat",
        )
        refresh_btn.grid(row=0, column=2, sticky="w")
        self._add_hover_effect(refresh_btn, self.accent_color, self.accent_hover)

        grid = tk.Frame(win, bg=self.bg_color)
        grid.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)

        # Overall donut chart
        overall_card = tk.Frame(
            grid, bg=self.card_color, highlightbackground=self.card_border, highlightthickness=1
        )
        overall_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=(0, 12))
        overall_card.rowconfigure(1, weight=1)
        tk.Label(
            overall_card,
            text="Réussite globale & objectif",
            font=("Helvetica", 14, "bold"),
            bg=self.card_color,
            fg=self.text_color,
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 6))
        self.dashboard_overall_canvas = tk.Canvas(
            overall_card, width=320, height=260, bg=self.card_color, highlightthickness=0
        )
        self.dashboard_overall_canvas.grid(row=1, column=0, sticky="nsew")

        # Trend chart
        trend_card = tk.Frame(
            grid, bg=self.card_color, highlightbackground=self.card_border, highlightthickness=1
        )
        trend_card.grid(row=0, column=1, sticky="nsew", padx=(12, 0), pady=(0, 12))
        trend_card.rowconfigure(1, weight=1)
        tk.Label(
            trend_card,
            text="Tendance de réussite (moyenne glissante)",
            font=("Helvetica", 14, "bold"),
            bg=self.card_color,
            fg=self.text_color,
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 6))
        self.dashboard_trend_canvas = tk.Canvas(
            trend_card, width=520, height=260, bg=self.card_color, highlightthickness=0
        )
        self.dashboard_trend_canvas.grid(row=1, column=0, sticky="nsew")

        # Theme breakdown
        theme_card = tk.Frame(
            grid, bg=self.card_color, highlightbackground=self.card_border, highlightthickness=1
        )
        theme_card.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        theme_card.rowconfigure(1, weight=1)
        tk.Label(
            theme_card,
            text="Répartition par thématique",
            font=("Helvetica", 14, "bold"),
            bg=self.card_color,
            fg=self.text_color,
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 6))
        self.dashboard_theme_canvas = tk.Canvas(
            theme_card, width=920, height=260, bg=self.card_color, highlightthickness=0
        )
        self.dashboard_theme_canvas.grid(row=1, column=0, sticky="nsew")

        self.refresh_dashboard()

    def refresh_dashboard(self) -> None:
        if not hasattr(self, "dashboard_win") or not self.dashboard_win.winfo_exists():
            return

        theme_filter = getattr(self, "dashboard_theme_var", tk.StringVar(value="Tous")).get()
        overall = self.stats.compute_overall(theme_filter)
        goal = self.stats.get_goal()
        trend_points = self.stats.moving_success(theme=theme_filter)
        breakdown = self.stats.theme_breakdown(theme=theme_filter if theme_filter != "Tous" else None)

        self._draw_overall_card(self.dashboard_overall_canvas, overall, goal)
        self._draw_trend_chart(self.dashboard_trend_canvas, trend_points)
        self._draw_theme_bars(self.dashboard_theme_canvas, breakdown)

    def _draw_overall_card(
        self, canvas: tk.Canvas, overall: Dict[str, Any], goal: Dict[str, Any]
    ) -> None:
        canvas.delete("all")
        width = int(canvas["width"])
        height = int(canvas["height"])
        cx, cy = width // 2, height // 2
        radius = min(width, height) // 2 - 24
        rate = overall.get("rate", 0)

        canvas.create_oval(
            cx - radius,
            cy - radius,
            cx + radius,
            cy + radius,
            outline="#e2e8f0",
            width=18,
        )
        canvas.create_arc(
            cx - radius,
            cy - radius,
            cx + radius,
            cy + radius,
            start=90,
            extent=-(rate / 100) * 360,
            style="arc",
            outline=self.accent_color,
            width=18,
            capstyle="round",
        )

        canvas.create_text(
            cx,
            cy - 6,
            text=f"{rate:.1f}%",
            font=("Helvetica", 28, "bold"),
            fill=self.text_color,
        )
        canvas.create_text(
            cx,
            cy + 26,
            text=f"{overall.get('correct', 0)}/{overall.get('total', 0)} bonnes réponses",
            font=("Helvetica", 11),
            fill=self.muted_text,
        )

        target = goal.get("target")
        if target is not None:
            delta = target - rate
            status = "Objectif atteint" if delta <= 0 else f"Encore {delta:.1f} pts"
            canvas.create_text(
                cx,
                height - 26,
                text=f"Objectif {target:.1f}% · {status}",
                font=("Helvetica", 11, "bold"),
                fill=self.correct_color if delta <= 0 else self.accent_color,
            )
        elif not overall.get("total"):
            canvas.create_text(
                cx,
                height - 26,
                text="Répondez à quelques questions pour voir vos progrès",
                font=("Helvetica", 11),
                fill=self.muted_text,
            )

    def _draw_trend_chart(self, canvas: tk.Canvas, points: List[tuple[int, float]]) -> None:
        canvas.delete("all")
        width = int(canvas["width"])
        height = int(canvas["height"])
        margin = 42

        canvas.create_rectangle(0, 0, width, height, fill=self.card_color, outline="")
        if not points:
            canvas.create_text(
                width // 2,
                height // 2,
                text="Pas encore de données pour tracer une tendance.",
                font=("Helvetica", 11),
                fill=self.muted_text,
            )
            return

        max_x = max(p[0] for p in points)
        min_y, max_y = 0, 100
        plot_w = width - margin * 2
        plot_h = height - margin * 2

        # Axes
        canvas.create_line(margin, height - margin, width - margin, height - margin, fill="#cbd5e1")
        canvas.create_line(margin, margin, margin, height - margin, fill="#cbd5e1")
        for y_step in range(0, 101, 20):
            y = height - margin - (y_step / (max_y - min_y)) * plot_h
            canvas.create_line(margin - 6, y, width - margin, y, fill="#e2e8f0")
            canvas.create_text(margin - 12, y, text=f"{y_step}%", anchor="e", fill=self.muted_text)

        coords = []
        for x_idx, rate in points:
            x = margin + (x_idx / max(1, max_x)) * plot_w
            y = height - margin - (rate / (max_y - min_y)) * plot_h
            coords.append((x, y))

        if len(coords) > 1:
            canvas.create_line(*sum(coords, ()), fill=self.accent_color, width=3, smooth=True)
        for x, y in coords[-15:]:
            canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill=self.accent_color, outline="")

        canvas.create_text(
            width // 2,
            margin - 12,
            text="Évolution des réponses correctes (moyenne glissante sur 5 questions)",
            font=("Helvetica", 11, "bold"),
            fill=self.text_color,
        )

    def _draw_theme_bars(self, canvas: tk.Canvas, breakdown: Dict[str, Dict[str, float]]) -> None:
        canvas.delete("all")
        width = int(canvas["width"])
        height = int(canvas["height"])
        margin = 60
        bar_gap = 16

        canvas.create_rectangle(0, 0, width, height, fill=self.card_color, outline="")
        if not breakdown:
            canvas.create_text(
                width // 2,
                height // 2,
                text="Aucune tentative pour afficher la répartition.",
                font=("Helvetica", 11),
                fill=self.muted_text,
            )
            return

        themes = list(sorted(breakdown.items(), key=lambda kv: kv[1].get("rate", 0), reverse=True))
        max_rate = max(stats.get("rate", 0) for _, stats in themes) or 1
        available_h = height - margin * 2
        bar_height = max(14, min(36, (available_h - bar_gap * (len(themes) - 1)) / len(themes)))

        for idx, (theme, stats) in enumerate(themes):
            y = margin + idx * (bar_height + bar_gap)
            rate = stats.get("rate", 0)
            correct = int(stats.get("correct", 0))
            total = int(stats.get("total", 0))
            bar_width = (rate / max_rate) * (width - margin * 2)

            canvas.create_rectangle(
                margin,
                y,
                margin + bar_width,
                y + bar_height,
                fill=self.accent_color,
                outline="",
            )
            canvas.create_rectangle(
                margin,
                y,
                width - margin,
                y + bar_height,
                outline="#e2e8f0",
                width=1,
            )
            canvas.create_text(
                margin + 6,
                y + bar_height / 2,
                text=f"{theme} — {rate:.1f}% ({correct}/{total})",
                anchor="w",
                fill="white" if rate > 15 else self.text_color,
                font=("Helvetica", 11, "bold"),
            )

        canvas.create_text(
            width // 2,
            margin - 16,
            text="Classement par thématique (taux de réussite)",
            font=("Helvetica", 11, "bold"),
            fill=self.text_color,
        )

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
        self.exam_mode = False
        self.stop_timer()
        self.timer_label.config(text="Timer: 00:00")
        self.current_theme = theme
        self.current_theme_label.config(text=f"Thematic: {theme}")
        self.exam_user_answers = []

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
        if self.exam_mode:
            self.feedback_label.config(
                text="Exam en cours : aucune correction avant la fin.",
                fg=self.muted_text,
            )
        else:
            self.feedback_label.config(text="")
        self.submit_btn.config(state="normal")
        self.next_btn.config(state="disabled")

    def start_exam_mode(self) -> None:
        """Start a mixed exam with 3 TF and 3 QCM questions across thematics."""
        tf_questions = [q for q in self.questions if q.category == "TF"]
        qcm_questions = [q for q in self.questions if q.category == "QCM"]

        if len(tf_questions) < 3 or len(qcm_questions) < 3:
            messagebox.showwarning(
                "Exam mode",
                "Not enough questions to start the exam (need at least 3 TF and 3 QCM).",
            )
            return

        selected = random.sample(tf_questions, 3) + random.sample(qcm_questions, 3)
        random.shuffle(selected)

        self.exam_mode = True
        self.exam_user_answers = [None for _ in selected]
        self.filtered_questions = selected
        self.current_theme = None
        self.current_theme_label.config(text="Exam mode: Mixed themes")
        self.score = 0
        self.total = 0
        self.current_index = 0
        self.update_score_label()
        self.feedback_label.config(
            text="Exam en cours : les corrections seront affichées à la fin.",
            fg=self.muted_text,
        )
        self.submit_btn.config(state="normal")
        self.next_btn.config(state="disabled")
        self.show_question()
        self.timer_label.config(text="Timer: 00:00")
        self.start_timer()

    def show_question(self) -> None:
        """Display current question and build answer widgets based on category."""
        if not self.filtered_questions:
            return

        if self.current_index >= len(self.filtered_questions):
            if self.exam_mode:
                self.finish_exam()
                return
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
        is_correct = False

        if self.exam_mode:
            # Save user answer without revealing correctness
            if q.category == "TF":
                user_answer: Union[bool, str] = selection == 0
            else:
                choices = q.choices or []
                if 0 <= selection < len(choices):
                    user_answer = choices[selection]
                else:
                    user_answer = ""

            self.exam_user_answers[self.current_index] = user_answer
            self.feedback_label.config(
                text="Réponse enregistrée. Les corrections seront affichées à la fin.",
                fg=self.muted_text,
            )
            self.submit_btn.config(state="disabled")

            if self.current_index == len(self.filtered_questions) - 1:
                self.finish_exam()
            else:
                self.next_btn.config(state="normal")
        else:
            if q.category == "TF":
                # index 0 → True, index 1 → False
                user_answer = (selection == 0)
                correct = bool(q.answer)  # type: ignore[arg-type]

                if user_answer == correct:
                    self.score += 1
                    is_correct = True
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
                    is_correct = True
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
            self.stats.record_attempt(q, bool(is_correct), source="practice")
            self.update_progress_card()
            self.refresh_dashboard()

    def on_next(self) -> None:
        """Go to next question in current thematic."""
        if not self.filtered_questions:
            return
        self.current_index += 1
        self.show_question()

    def start_timer(self) -> None:
        self.timer_start = time.perf_counter()
        self.timer_running = True
        self._update_timer()

    def stop_timer(self) -> None:
        self.timer_running = False

    def _update_timer(self) -> None:
        if not self.timer_running:
            return

        elapsed = int(time.perf_counter() - self.timer_start)
        minutes, seconds = divmod(elapsed, 60)
        hours, minutes = divmod(minutes, 60)
        self.timer_label.config(text=f"Timer: {hours:02d}:{minutes:02d}:{seconds:02d}")
        self.after(1000, self._update_timer)

    def update_score_label(self) -> None:
        """Update score display."""
        self.score_label.config(text=f"Score: {self.score} / {self.total}")

    def finish_exam(self) -> None:
        """Compute score and show corrections at the end of the exam mode."""
        if not self.exam_mode:
            return

        self.stop_timer()
        total_questions = len(self.filtered_questions)
        correct_count = 0
        corrections = []

        for idx, q in enumerate(self.filtered_questions):
            user_answer = self.exam_user_answers[idx]
            if q.category == "TF":
                correct_answer: Union[bool, str] = bool(q.answer)  # type: ignore[arg-type]
                is_correct = user_answer == correct_answer
                correct_display = "True" if correct_answer else "False"
                if user_answer is None:
                    user_display = "Non répondu"
                    is_correct = False
                else:
                    user_display = "True" if user_answer else "False"
            else:
                correct_answer = str(q.answer)
                is_correct = user_answer == correct_answer
                if user_answer is None:
                    user_display = "Non répondu"
                    is_correct = False
                else:
                    user_display = str(user_answer or "")
                correct_display = correct_answer

            if is_correct:
                correct_count += 1
            self.stats.record_attempt(q, bool(is_correct), source="exam")

            corrections.append(
                f"Q{idx + 1} ({q.category} - {q.thematic}): {q.question}\n"
                f"  Votre réponse : {user_display}\n"
                f"  Réponse attendue : {correct_display}\n"
                f"  Statut : {'✅ Correct' if is_correct else '❌ Incorrect'}\n"
            )

        self.score = correct_count
        self.total = total_questions
        percent = (correct_count / total_questions) * 100 if total_questions else 0
        self.exam_mode = False
        self.update_score_label()
        self.feedback_label.config(
            text=f"Exam terminé – Score: {percent:.1f}% ({correct_count}/{total_questions})",
            fg=self.text_color,
        )
        self.submit_btn.config(state="disabled")
        self.next_btn.config(state="disabled")

        summary_window = tk.Toplevel(self)
        summary_window.title("Résultats de l'examen")
        summary_window.geometry("750x500")

        title = tk.Label(
            summary_window,
            text=f"Score: {percent:.1f}%   |   Temps écoulé: {self.timer_label.cget('text').split(': ',1)[1]}",
            font=("Helvetica", 13, "bold"),
        )
        title.pack(pady=10)

        text_widget = tk.Text(
            summary_window,
            wrap="word",
            font=("Helvetica", 11),
            padx=12,
            pady=12,
        )
        text_widget.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        text_widget.insert("1.0", "\n".join(corrections))
        text_widget.config(state="disabled")
        self.update_progress_card()
        self.refresh_dashboard()


def main() -> None:
    app = QuizApp("mmc_questions.json")
    app.mainloop()


if __name__ == "__main__":
    main()
