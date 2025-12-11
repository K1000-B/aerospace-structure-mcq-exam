# Aerospace Structure MCQ Trainer

Desktop trainer to rehearse MMC-style multiple-choice and true/false questions. The app runs locally with Tkinter and keeps track of your progress between sessions.

## Requirements
- Python 3.10+ with the built-in Tkinter library (comes by default on macOS and most Linux distributions; on Windows use the standard Python installer).
- No external dependencies or internet connection needed.

## Quick start
1) Download/clone the repository.
2) Open a terminal **in the project folder** (the one containing `main.py`).
3) Run:
```bash
python main.py
```
If `python` points to Python 2 on your machine, use `python3 main.py` instead. Your progress is saved to `data/personnal_data/progress_data.json` (created automatically).

### If you do not use Anaconda
- **macOS with Python from python.org**: install Python from https://www.python.org/downloads/, then in Terminal run `python3 main.py`. The installer usually sets up `python3` and `pip3`.
- **Windows with Python from python.org**: install from https://www.python.org/downloads/windows/ and check “Add Python to PATH” during setup. Then in Command Prompt or PowerShell run `python main.py`. If that fails, try `py main.py`.

### macOS without Python installed
Install via Homebrew, then run the app:
```bash
brew install python
python3 main.py
```
(If you just installed Homebrew, follow its post-install instructions first.)

### macOS: make `python` point to Homebrew’s Python
If your Python is at `/usr/local/bin/python3` (common with Homebrew) and you want a shorter command, add an alias in your shell profile:
```bash
echo "alias python=/usr/local/bin/python3" >> ~/.zshrc   # for zsh (default on macOS)
echo "alias python=/usr/local/bin/python3" >> ~/.bash_profile   # for bash
```
Then reload your shell (`source ~/.zshrc` or `source ~/.bash_profile`) and use `python main.py`. Without the alias, just run `python3 main.py`.

### macOS: alias even without Homebrew
If you installed Python manually (e.g., from python.org) and it lives at `/usr/local/bin/python3`, you can set aliases for both Python and pip:
```bash
nano ~/.zshrc
alias python3="/usr/local/bin/python3"
alias pip="/usr/local/bin/pip3"
source ~/.zshrc
```
Open a new terminal or run the `source` line to apply the aliases, then use `python3 main.py` (or `python main.py` if you also add `alias python=/usr/local/bin/python3`).

### Anaconda users
If your prompt shows `(base)`, you are already in the default Anaconda environment. Run:
```bash
python main.py
```
If you prefer a clean environment, create one with `conda create -n qcm python=3.11`, activate it with `conda activate qcm`, then run `python main.py`.

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
