"""Packaging configuration for building a macOS .app with py2app."""

from setuptools import setup


APP = ["main.py"]
DATA_FILES = [
    "mmc_questions.json",
    "progress_data.json",
    "question_editor.py",
]
OPTIONS = {
    "iconfile": "icon.icns",
    "argv_emulation": False,
    # Explicitly include tkinter to avoid stripping
    "packages": ["tkinter"],
    "frameworks": [
    "/Users/camile/anaconda3/lib/libffi.8.dylib",
    "/Users/camile/anaconda3/lib/libffi.7.dylib",
    "/Users/camile/anaconda3/lib/libtk8.6.dylib",
    "/Users/camile/anaconda3/lib/libtcl8.6.dylib",
],

}


if __name__ == "__main__":
    setup(
        app=APP,
        data_files=DATA_FILES,
        options={"py2app": OPTIONS},
        setup_requires=["py2app"],
    )
