# aerospace-structure-mcq-exam

App for training on MCQ of past exams.

## Ajouter des questions

L'outil `question_editor.py` fournit une petite interface Tkinter pour ajouter des questions à `mmc_questions.json`:

```bash
python question_editor.py
```

Sélectionnez le type de question (TF ou QCM), saisissez l'énoncé, les réponses et enregistrez ; le fichier JSON est mis à jour immédiatement.

## Construire l'app macOS (.app)

1. Installez py2app (dans votre environnement Python) : `pip install py2app`
2. Depuis la racine du projet, construisez : `python setup.py py2app`
3. Le bundle sera généré dans `dist/main.app` avec les fichiers `mmc_questions.json`, `progress_data.json` et `question_editor.py` intégrés, ainsi que l'icône `icon.icns`.
