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
import subprocess
import sys
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

    # Optional explanation shown when the answer is incorrect
    explication: Optional[str] = None


# ---------- Persistent stats manager ----------


class StatsManager:
    def __init__(self, storage_path: Path):
        self.storage_path = Path(storage_path)
        self.data: Dict[str, Any] = {
            "attempts": [],
            "goals": [],
            "active_goal_id": None,
        }
        self.load()

    # ---------- Persistence ----------
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
                        "goals": [],
                        "active_goal_id": None,
                    }

        # Migration from legacy single-goal format
        legacy_goal = self.data.get("goal")  # keep key for backward readability
        goals = self.data.get("goals")
        if not isinstance(goals, list):
            goals = []
        if goals == [] and isinstance(legacy_goal, dict):
            try:
                tgt = legacy_goal.get("target")
            except AttributeError:
                tgt = None
            if tgt is not None:
                goals.append(
                    {
                        "id": 1,
                        "target": float(tgt),
                        "label": legacy_goal.get("label", ""),
                    }
                )
                self.data["active_goal_id"] = 1
        self.data["goals"] = goals
        self.data.setdefault("active_goal_id", None)
        self.data.setdefault("attempts", [])
        if goals and self.data.get("active_goal_id") is None:
            self.data["active_goal_id"] = goals[0].get("id")

    def save(self) -> None:
        # Keep the legacy "goal" key in sync with the active goal for compatibility
        active_goal = self.get_goal()
        self.data["goal"] = (
            {"target": active_goal["target"], "label": active_goal.get("label", "")}
            if active_goal
            else {"target": None, "label": ""}
        )
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

    # ---------- Goals ----------
    def _next_goal_id(self) -> int:
        existing = [g.get("id", 0) for g in self.data.get("goals", [])]
        return (max(existing) if existing else 0) + 1

    def list_goals(self) -> List[Dict[str, Any]]:
        return list(self.data.get("goals", []))

    def get_goal(self, goal_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        goals = self.data.get("goals", [])
        target_id = goal_id if goal_id is not None else self.data.get("active_goal_id")
        if target_id is None:
            return None
        for g in goals:
            if g.get("id") == target_id:
                return g
        return None

    def set_goal(self, target_percent: float, label: str = "") -> int:
        """Legacy helper: create/update the active goal."""
        if self.data.get("active_goal_id") is None and self.data.get("goals"):
            active_id = self.data["goals"][0]["id"]
        else:
            active_id = self.data.get("active_goal_id") or self._next_goal_id()

        existing = self.get_goal(active_id)
        if existing:
            existing["target"] = float(target_percent)
            existing["label"] = label
        else:
            self.data.setdefault("goals", []).append(
                {"id": active_id, "target": float(target_percent), "label": label}
            )
        self.data["active_goal_id"] = active_id
        self.save()
        return active_id

    def add_goal(self, target_percent: float, label: str = "") -> int:
        goal_id = self._next_goal_id()
        self.data.setdefault("goals", []).append(
            {"id": goal_id, "target": float(target_percent), "label": label}
        )
        if self.data.get("active_goal_id") is None:
            self.data["active_goal_id"] = goal_id
        self.save()
        return goal_id

    def update_goal(self, goal_id: int, target_percent: float, label: str = "") -> None:
        goal = self.get_goal(goal_id)
        if not goal:
            return
        goal["target"] = float(target_percent)
        goal["label"] = label
        self.save()

    def delete_goal(self, goal_id: int) -> None:
        goals = self.data.get("goals", [])
        self.data["goals"] = [g for g in goals if g.get("id") != goal_id]
        if self.data.get("active_goal_id") == goal_id:
            self.data["active_goal_id"] = self.data["goals"][0]["id"] if self.data["goals"] else None
        self.save()

    def set_active_goal(self, goal_id: Optional[int]) -> None:
        if goal_id is None:
            self.data["active_goal_id"] = None
        elif any(g.get("id") == goal_id for g in self.data.get("goals", [])):
            self.data["active_goal_id"] = goal_id
        self.save()

    def get_active_goal_id(self) -> Optional[int]:
        return self.data.get("active_goal_id")

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
        self.json_path = json_path
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
        self.editor_processes: List[subprocess.Popen] = []

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
                explication = item.get("explication")
                if isinstance(explication, str):
                    explication = explication.strip()
                else:
                    explication = None

                q = Question(
                    id=int(item["id"]),
                    category=item["category"],
                    thematic=item["thematic"],
                    question=item["question"],
                    choices=item.get("choices"),
                    answer=item["answer"],
                    explication=explication,
                )
                self.questions.append(q)

            # Unique thematics
            self.themes = sorted({q.thematic for q in self.questions})
            self._refresh_theme_listbox()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load questions:\n{e}")
            self.destroy()

    def refresh_questions_from_file(self) -> None:
        """Reload questions after edits in the external editor."""
        prev_theme = self.current_theme
        self.load_questions(self.json_path)
        if prev_theme and prev_theme in self.themes:
            self.current_theme = prev_theme
        else:
            self.current_theme = None
            self.current_theme_label.config(text="No thematic selected")
        self.refresh_dashboard()

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
        self._refresh_theme_listbox()

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

        question_editor_btn = tk.Button(
            left_panel,
            text="Ajouter des questions",
            command=self.open_question_editor,
            bg="#f97316",
            fg="#0b2b1f",
            bd=0,
            font=("Helvetica", 11, "bold"),
            activebackground="#ea580c",
            activeforeground="#0b2b1f",
            padx=12,
            pady=8,
            relief="flat",
            cursor="hand2",
        )
        question_editor_btn.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 16))
        self._add_hover_effect(question_editor_btn, "#f97316", "#ea580c")

        progress_card = tk.Frame(
            left_panel,
            bg="#eef2ff",
            bd=0,
            highlightthickness=1,
            highlightbackground=self.card_border,
        )
        progress_card.grid(row=5, column=0, sticky="nsew", padx=16, pady=(0, 16))
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
            wraplength=680,
            justify="left",
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

        self.explanation_label = tk.Label(
            bottom_bar,
            text="",
            font=("Helvetica", 10),
            fg=self.muted_text,
            bg=self.card_color,
            wraplength=780,
            justify="left",
        )
        self.explanation_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))

    def _refresh_theme_listbox(self) -> None:
        """Keep the theme selector in sync with loaded questions."""
        if not hasattr(self, "theme_listbox"):
            return
        current_selection = None
        try:
            sel = self.theme_listbox.curselection()
            if sel:
                current_selection = self.theme_listbox.get(sel[0])
        except Exception:
            current_selection = None

        self.theme_listbox.delete(0, tk.END)
        for t in self.themes:
            self.theme_listbox.insert(tk.END, t)

        if current_selection and current_selection in self.themes:
            idx = self.themes.index(current_selection)
            self.theme_listbox.selection_set(idx)
            self.theme_listbox.see(idx)

    def open_question_editor(self) -> None:
        """Launch the external question editor window."""
        editor_path = Path(__file__).with_name("question_editor.py")
        if not editor_path.exists():
            messagebox.showerror("Éditeur de questions", "Le fichier question_editor.py est introuvable.")
            return
        try:
            proc = subprocess.Popen([sys.executable, str(editor_path)])
            self.editor_processes.append(proc)
            # Poll the editor process to reload questions once it exits
            self.after(1500, self._watch_question_editor)
        except Exception as exc:  # pragma: no cover - UI only
            messagebox.showerror("Éditeur de questions", f"Impossible d'ouvrir l'éditeur : {exc}")

    def _watch_question_editor(self) -> None:
        """Reload questions when the external editor window is closed."""
        if not self.editor_processes:
            return
        alive = []
        changed = False
        for proc in self.editor_processes:
            if proc.poll() is None:
                alive.append(proc)
            else:
                changed = True
        self.editor_processes = alive

        if changed:
            self.refresh_questions_from_file()

        if self.editor_processes:
            self.after(1500, self._watch_question_editor)

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

        if not goal or goal.get("target") is None:
            goal_text = "Objectif actif : aucun"
        else:
            goal_target = goal.get("target")
            delta = goal_target - overall.get("rate", 0)
            if delta <= 0:
                goal_text = f"Objectif atteint ({goal_target:.1f}%). Bravo !"
            else:
                goal_text = f"Objectif : {goal_target:.1f}% (encore {delta:.1f} pts)"

            label = goal.get("label") or f"Objectif {goal.get('id')}"
            if label:
                goal_text += f"\n“{label}”"

        self.goal_status_label.config(text=goal_text)

    def _goal_display_text(self, goal: Dict[str, Any]) -> str:
        label = goal.get("label") or "Objectif sans nom"
        target = goal.get("target")
        target_text = f"{target:.1f}%" if target is not None else "—"
        return f"{label} ({target_text})"

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

    def _refresh_dashboard_goal_menu(self, selected: Optional[int] = None) -> None:
        """Keep the dashboard goal selector in sync with stored objectives."""
        if not hasattr(self, "dashboard_goal_var") or not hasattr(self, "dashboard_goal_menu"):
            return

        try:
            menu = self.dashboard_goal_menu["menu"]
        except Exception:
            return

        goals = self.stats.list_goals()
        menu.delete(0, "end")
        menu.add_command(label="Aucun objectif", command=lambda v="none": self.dashboard_goal_var.set(v))

        for g in goals:
            gid = str(g.get("id"))
            label = self._goal_display_text(g)
            menu.add_command(label=label, command=lambda v=gid: self.dashboard_goal_var.set(v))

        if selected is not None:
            self.dashboard_goal_var.set(str(selected))
        else:
            active_id = self.stats.get_active_goal_id()
            if active_id is not None:
                self.dashboard_goal_var.set(str(active_id))
            elif goals:
                self.dashboard_goal_var.set(str(goals[0].get("id")))
            else:
                self.dashboard_goal_var.set("none")

    def show_stats_window(self) -> None:
        win = tk.Toplevel(self)
        win.title("Suivi des performances")
        win.geometry("520x520")

        header = tk.Label(
            win,
            text="Suivi détaillé",
            font=("Helvetica", 14, "bold"),
        )
        header.pack(pady=(12, 6))

        summary_label = tk.Label(
            win,
            text="",
            justify="left",
            wraplength=480,
        )
        summary_label.pack(padx=12, pady=(0, 10), anchor="w")

        theme_stats = tk.Label(
            win,
            text="",
            justify="left",
            wraplength=480,
            anchor="w",
        )
        theme_stats.pack(padx=12, pady=(0, 10), anchor="w")

        goal_frame = tk.LabelFrame(win, text="Objectifs", padx=10, pady=8)
        goal_frame.pack(fill="x", padx=12, pady=6)
        goal_frame.columnconfigure(1, weight=1)

        tk.Label(goal_frame, text="Objectif affiché :", anchor="w").grid(row=0, column=0, sticky="w")
        self.stats_goal_var = tk.StringVar(value="new")
        goal_menu = tk.OptionMenu(goal_frame, self.stats_goal_var, "")
        goal_menu.config(bg="#e0f2fe", fg=self.text_color, bd=0, highlightthickness=0)
        goal_menu.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        tk.Label(goal_frame, text="(affiche le nom de l'objectif)", fg=self.muted_text).grid(
            row=0, column=2, sticky="w", padx=(8, 0)
        )

        tk.Label(goal_frame, text="Taux cible (%) :").grid(row=1, column=0, sticky="w", pady=(6, 0))
        goal_entry = tk.Entry(goal_frame)
        goal_entry.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))

        tk.Label(goal_frame, text="Nom de l'objectif :").grid(row=2, column=0, sticky="w")
        label_entry = tk.Entry(goal_frame)
        label_entry.grid(row=2, column=1, sticky="ew", padx=(6, 0), pady=(4, 0))

        feedback_label = tk.Label(goal_frame, text="", fg=self.correct_color, anchor="w", justify="left")
        feedback_label.grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))

        def current_goal_id() -> Optional[int]:
            val = self.stats_goal_var.get()
            if val in ("", "new", "none"):
                return None
            try:
                return int(val)
            except ValueError:
                return None

        def load_selected_goal() -> None:
            goal_id = current_goal_id()
            if goal_id is None:
                goal_entry.delete(0, tk.END)
                label_entry.delete(0, tk.END)
                feedback_label.config(text="Nouveau objectif. Renseignez les champs puis enregistrez.")
                return
            goal = self.stats.get_goal(goal_id)
            if goal:
                goal_entry.delete(0, tk.END)
                goal_entry.insert(0, f"{goal.get('target', 0):.1f}")
                label_entry.delete(0, tk.END)
                if goal.get("label"):
                    label_entry.insert(0, goal.get("label"))
                feedback_label.config(text=f"Objectif #{goal_id} chargé.")

        def refresh_goal_menu(selected: Optional[str] = None) -> None:
            goals = self.stats.list_goals()
            menu = goal_menu["menu"]
            menu.delete(0, "end")
            menu.add_command(
                label="Créer un nouvel objectif",
                command=lambda v="new": (self.stats_goal_var.set(v), load_selected_goal()),
            )
            for g in goals:
                gid = str(g.get("id"))
                label = self._goal_display_text(g)
                menu.add_command(
                    label=label, command=lambda v=gid: (self.stats_goal_var.set(v), load_selected_goal())
                )

            active_id = self.stats.get_active_goal_id()
            if selected is not None:
                self.stats_goal_var.set(selected)
            elif goals:
                default_val = str(active_id) if active_id is not None else str(goals[0]["id"])
                self.stats_goal_var.set(default_val)
            else:
                self.stats_goal_var.set("new")
            load_selected_goal()
            try:
                sel_id = int(self.stats_goal_var.get())
            except ValueError:
                sel_id = None
            self._refresh_dashboard_goal_menu(sel_id)

        def save_goal(is_new: bool = False) -> None:
            try:
                target = float(goal_entry.get())
            except ValueError:
                feedback_label.config(text="Veuillez saisir un pourcentage valide.", fg=self.wrong_color)
                return

            label_val = label_entry.get().strip()
            goal_id = current_goal_id()
            if is_new or goal_id is None:
                new_id = self.stats.add_goal(target, label_val)
                refresh_goal_menu(str(new_id))
                feedback_label.config(text="Objectif créé et sélectionné.", fg=self.correct_color)
            else:
                self.stats.update_goal(goal_id, target, label_val)
                refresh_goal_menu(str(goal_id))
                feedback_label.config(text="Objectif mis à jour.", fg=self.correct_color)
            self.update_progress_card()
            self.refresh_dashboard()
            self._refresh_dashboard_goal_menu(current_goal_id())
            refresh_summary()

        def set_active_goal() -> None:
            goal_id = current_goal_id()
            if goal_id is None:
                feedback_label.config(text="Sélectionnez un objectif existant.", fg=self.wrong_color)
                return
            self.stats.set_active_goal(goal_id)
            feedback_label.config(text="Objectif actif mis à jour.", fg=self.correct_color)
            self.update_progress_card()
            self.refresh_dashboard()
            self._refresh_dashboard_goal_menu(goal_id)
            refresh_summary()

        def delete_goal() -> None:
            goal_id = current_goal_id()
            if goal_id is None:
                feedback_label.config(text="Aucun objectif à supprimer.", fg=self.wrong_color)
                return
            self.stats.delete_goal(goal_id)
            refresh_goal_menu()
            feedback_label.config(text="Objectif supprimé.", fg=self.correct_color)
            self.update_progress_card()
            self.refresh_dashboard()
            self._refresh_dashboard_goal_menu()
            refresh_summary()

        btns = tk.Frame(goal_frame, bg=self.card_color)
        btns.grid(row=3, column=0, columnspan=2, sticky="e", pady=(8, 0))

        create_btn = tk.Button(
            btns,
            text="Nouveau",
            command=lambda: (self.stats_goal_var.set("new"), load_selected_goal()),
            bg="#e0f2fe",
            fg=self.text_color,
            bd=0,
            font=("Helvetica", 10, "bold"),
            padx=8,
            pady=6,
            relief="flat",
        )
        create_btn.grid(row=0, column=0, padx=(0, 6))

        save_btn = tk.Button(
            btns,
            text="Enregistrer",
            command=lambda: save_goal(is_new=False),
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
        save_btn.grid(row=0, column=1, padx=(0, 6))
        self._add_hover_effect(save_btn, self.accent_color, self.accent_hover)

        add_btn = tk.Button(
            btns,
            text="Créer",
            command=lambda: save_goal(is_new=True),
            bg="#0ea5e9",
            fg="#0b2b1f",
            bd=0,
            font=("Helvetica", 10, "bold"),
            activebackground="#0284c7",
            activeforeground="#0b2b1f",
            padx=8,
            pady=6,
            relief="flat",
        )
        add_btn.grid(row=0, column=2, padx=(0, 6))
        self._add_hover_effect(add_btn, "#0ea5e9", "#0284c7")

        activate_btn = tk.Button(
            btns,
            text="Définir comme actif",
            command=set_active_goal,
            bg="#10b981",
            fg="#0b2b1f",
            bd=0,
            font=("Helvetica", 10, "bold"),
            activebackground="#059669",
            activeforeground="#0b2b1f",
            padx=8,
            pady=6,
            relief="flat",
        )
        activate_btn.grid(row=0, column=3, padx=(0, 6))
        self._add_hover_effect(activate_btn, "#10b981", "#059669")

        delete_btn = tk.Button(
            btns,
            text="Supprimer",
            command=delete_goal,
            bg="#fca5a5",
            fg="#7f1d1d",
            bd=0,
            font=("Helvetica", 10, "bold"),
            activebackground="#ef4444",
            activeforeground="white",
            padx=8,
            pady=6,
            relief="flat",
        )
        delete_btn.grid(row=0, column=4)
        self._add_hover_effect(delete_btn, "#fca5a5", "#ef4444")

        def refresh_summary() -> None:
            overall = self.stats.compute_overall()
            progress_delta = self.stats.progress_speed()

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
            summary_label.config(text=summary_text)
            theme_stats.config(text=self._render_theme_stats())

            goal_id = current_goal_id()
            goal = self.stats.get_goal(goal_id) if goal_id is not None else self.stats.get_goal()
            if goal and goal.get("target") is not None:
                feedback_label.config(
                    text=f"Objectif affiché : {self._goal_display_text(goal)}",
                    fg=self.correct_color,
                )
            elif self.stats.list_goals():
                feedback_label.config(text="Sélectionnez ou créez un objectif.", fg=self.muted_text)

        refresh_goal_menu()
        refresh_summary()

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

        tk.Label(
            controls, text="Objectif affiché :", bg=self.bg_color, fg=self.text_color
        ).grid(row=0, column=2, sticky="w")
        self.dashboard_goal_var = tk.StringVar(value="none")
        self.dashboard_goal_menu = tk.OptionMenu(controls, self.dashboard_goal_var, "")
        self.dashboard_goal_menu.config(bg="#e0f2fe", fg=self.text_color, bd=0, highlightthickness=0)
        self.dashboard_goal_menu.grid(row=0, column=3, sticky="w", padx=(8, 16))
        self.dashboard_goal_var.trace_add("write", lambda *_: self.refresh_dashboard())

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
        refresh_btn.grid(row=0, column=4, sticky="w")
        self._add_hover_effect(refresh_btn, self.accent_color, self.accent_hover)
        controls.columnconfigure(4, weight=1)

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

        self._refresh_dashboard_goal_menu()
        self.refresh_dashboard()

    def refresh_dashboard(self) -> None:
        if not hasattr(self, "dashboard_win") or not self.dashboard_win.winfo_exists():
            return

        theme_filter = getattr(self, "dashboard_theme_var", tk.StringVar(value="Tous")).get()
        goal_val = getattr(self, "dashboard_goal_var", tk.StringVar(value="none")).get()
        pre_selected_goal_id = None
        try:
            pre_selected_goal_id = int(goal_val) if goal_val not in ("none", "") else None
        except ValueError:
            pre_selected_goal_id = None

        self._refresh_dashboard_goal_menu(pre_selected_goal_id)
        goal_val = getattr(self, "dashboard_goal_var", tk.StringVar(value="none")).get()
        try:
            goal_id = int(goal_val) if goal_val not in ("none", "") else None
        except ValueError:
            goal_id = None

        overall = self.stats.compute_overall(theme_filter)
        goal = self.stats.get_goal(goal_id) if goal_id is not None else self.stats.get_goal()
        trend_points = self.stats.moving_success(theme=theme_filter)
        breakdown = self.stats.theme_breakdown(theme=theme_filter if theme_filter != "Tous" else None)

        self._draw_overall_card(self.dashboard_overall_canvas, overall, goal)
        self._draw_trend_chart(self.dashboard_trend_canvas, trend_points)
        self._draw_theme_bars(self.dashboard_theme_canvas, breakdown)

    def _draw_overall_card(
        self, canvas: tk.Canvas, overall: Dict[str, Any], goal: Optional[Dict[str, Any]]
    ) -> None:
        canvas.delete("all")
        width = int(canvas["width"])
        height = int(canvas["height"])
        cx, cy = width // 2, height // 2
        radius = min(width, height) // 2 - 24
        rate = overall.get("rate", 0)
        total = overall.get("total", 0)

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

        target = goal.get("target") if goal else None
        goal_label = self._goal_display_text(goal) if goal else "Aucun objectif"
        if target is not None:
            delta = target - rate
            status = "Objectif atteint" if delta <= 0 else f"Encore {delta:.1f} pts"
            canvas.create_text(
                cx,
                height - 26,
                text=f"{goal_label} · {status}",
                font=("Helvetica", 11, "bold"),
                fill=self.correct_color if delta <= 0 else self.accent_color,
            )
        elif not total:
            canvas.create_text(
                cx,
                height - 26,
                text="Répondez à quelques questions pour voir vos progrès",
                font=("Helvetica", 11),
                fill=self.muted_text,
            )
        else:
            canvas.create_text(
                cx,
                height - 26,
                text=f"{goal_label}",
                font=("Helvetica", 11, "bold"),
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

    def _clear_explanation(self) -> None:
        if hasattr(self, "explanation_label"):
            self.explanation_label.config(text="")

    def _get_explanation_text(self, question: Question) -> str:
        raw = question.explication or ""
        return raw.strip()

    def _maybe_show_explanation(self, question: Question, is_correct: bool) -> None:
        explanation = self._get_explanation_text(question)
        if (not is_correct) and explanation:
            self.explanation_label.config(
                text=f"Explication : {explanation}",
                fg=self.muted_text,
            )
        else:
            self._clear_explanation()

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

        self._clear_explanation()
        self.question_label.config(
            text=f"Q{self.current_index + 1} (ID {q.id}): {q.question}"
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
        self._clear_explanation()

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
            self._clear_explanation()

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

            self._maybe_show_explanation(q, bool(is_correct))
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

        self._clear_explanation()
        self.stop_timer()
        total_questions = len(self.filtered_questions)
        correct_count = 0
        corrections = []

        for idx, q in enumerate(self.filtered_questions):
            user_answer = self.exam_user_answers[idx]
            explanation = self._get_explanation_text(q)
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

            lines = [
                f"Q{idx + 1} ({q.category} - {q.thematic}): {q.question}",
                f"  Votre réponse : {user_display}",
                f"  Réponse attendue : {correct_display}",
                f"  Statut : {'✅ Correct' if is_correct else '❌ Incorrect'}",
            ]
            if (not is_correct) and explanation:
                lines.append(f"  Explication : {explanation}")

            corrections.append("\n".join(lines) + "\n")

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
