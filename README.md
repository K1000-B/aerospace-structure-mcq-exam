# Aerospace Structure MCQ Trainer

Desktop trainer to rehearse MMC-style multiple-choice and true/false questions. The app runs locally with Tkinter and keeps track of your progress between sessions.

## Requirements
- Python 3.10+ with the built-in Tkinter library (comes by default on macOS and most Linux distributions; on Windows use the standard Python installer).
- No external dependencies or internet connection needed.

## Quick start
1) Download/clone the repository.  
2) From the project root, launch the trainer:
```bash
python main.py
```
Your progress is saved to `data/personnal_data/progress_data.json` (created automatically).

## Using the trainer
- Pick a thematic in the left list, then click the start button to get shuffled questions from that theme.
- For each question, select an answer and submit. Feedback (and explanations when available) appears under the question.
- `Next` moves to another question. When a thematic finishes, questions reshuffle so you can keep practicing.
- `Exam mode` mixes 3 TF and 3 QCM questions across thematics, hides feedback until the end, and includes a timer.

## Add or edit questions with the GUI
Run the editor to maintain the question bank in `data/mmc_questions.json`:
```bash
python question_editor.py
```
- Choose the category (`TF` or `QCM`), set the thematic, and enter the statement.
- For QCM, list the answer choices and select the correct one.
- Click save; the JSON file updates immediately and the main app can reload it.

## Question file format (manual edits)
Questions live in `data/mmc_questions.json` under the `questions` list:
```json
{
  "questions": [
    {
      "id": 1,
      "category": "TF",
      "thematic": "Buckling & Stability",
      "question": "Statement text...",
      "choices": null,
      "answer": false,
      "explication": "Optional explanation shown when the answer is wrong."
    }
  ]
}
```
- `id` must be unique and numeric.  
- `category` is `TF` or `QCM`.  
- `choices` is `null` for TF and a list of strings for QCM.  
- `answer` is `true/false` for TF or the exact string of the correct choice for QCM.  
- `explication` (optional) appears when the user answers incorrectly.

## Resetting progress
Delete `data/personnal_data/progress_data.json` if you want to start over with a clean history. The file will be recreated on the next launch.
