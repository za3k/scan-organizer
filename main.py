#!/usr/bin/env python3
import functools
import os
import pathlib
import subprocess
import sys

from organize import Organizer


class ScanOrganizer(Organizer):
    """
    Phase 1 [-cleaned]: Clean up pictures. +cleaned
    Phase 2 [-categorized]: Categorize pictures (sort into folders). +categorized
    Phase 3 [-named +categorized]: Name files. +named
    Phase 4 [-hand_transcribe -computer_transcribe -no_text]: Tag files as needing transcription.
    Phase 5 [+hand_transcribe -transcribed]: Transcribe files by hand. +transcribed
    """
    def __init__(self):
        super().__init__()

        self.add_phase(
            name="Phase 1: Clean",
            tags=["-cleaned"],
            extras=[],
            buttons={
                "Rotate left": self.rotate_left,
                "Rotate right": self.rotate_right,
                "Crop": self.crop,
                "Skip Prev": self.prev,
                "Skip Next": self.next,
                "Done": functools.partial(self.tag, "+cleaned"),
            },
        )
        self.add_phase(
            name="Phase 2: Categorize",
            tags=["-categorized"],
            extras=["categories"],
            buttons={
                "Skip Prev": self.prev,
                "Skip Next": self.next,
                "Categorize": [self.set_category, functools.partial(self.tag, "+categorized")],
            },
        )
        self.add_phase(
            name="Phase 3: Renaming",
            tags=["-named","+categorized"],
            extras=["rename", "current_category"],
            buttons={
                "Rename": [self.set_name, functools.partial(self.tag, "+named")],
            },
        )
        self.add_phase(
            name="Phase 4: Tagging",
            tags=["-hand_transcribe", "-computer_transcribe", "-no_text", "-text_elsewhere"],
            extras=[],
            buttons={
                "No text": [functools.partial(self.tag, "+no_text")],
                "Very short": [functools.partial(self.tag, "+hand_transcribe")],
                "Handwritten text": [functools.partial(self.tag, "+hand_transcribe")],
                "Computer font": [functools.partial(self.tag, "+computer_transcribe")],
                "Text stored elsewhere": [functools.partial(self.tag, "+text_elsewhere")],
                "Skip Prev": self.prev,
                "Skip Next": self.next,
            },
        )
        self.add_phase(
            name="Phase 5: Transcription",
            tags=["+hand_transcribe", "-transcribed"],
            extras=["transcribe"],
            buttons={
                "Skip Prev": self.prev,
                "Skip Next": self.next,
                "Transcribed": [self.save_transcription, functools.partial(self.tag, "+transcribed")],
            },
        )

    def load_master(self, master):
        files = []
        dirs = [master]
        for p in dirs:
            assert p.is_dir()
            for x in p.iterdir():
                if x.is_file():
                    files.append(x)
                elif x.is_dir():
                    dirs.append(x)

        for category in dirs:
            organizer.add_category(category, str(category.relative_to(master)))
        # TODO: natsort filenames and categories. how to deal with file renames?
        for file in files:
            if file.suffix in {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".gif"}:
                organizer.add_image(file)
        organizer.autoselect_phase()

    def _run(self, command):
        """Run an external command"""
        done = subprocess.run(command)
        return done.returncode == 0

    # Application-specific buttons
    def rotate_left(self, _, image):
        print("rotate_left")
        self._run(["convert", image.image_path, "-rotate", "270", image.image_path])
        self.reload_image(image)

    def rotate_right(self, _, image):
        print("rotate_right")
        self._run(["convert", image.image_path, "-rotate", "90", image.image_path])
        self.reload_image(image)

    def crop(self, _, image):
        print("crop")
        success = self._run(["cropgui", image.image_path]) # Only works on jpg
        if success:
            new_path = image.image_path.parent.joinpath("{}-crop{}".format(image.image_path.stem, image.image_path.suffix))
            os.rename(new_path, image.image_path)
            self.reload_image(image)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        master = pathlib.Path(os.getcwd())
    elif len(sys.argv) == 2:
        master = pathlib.Path(sys.argv[1])
    else:
        print("Too many paths"); sys.exit(1)
    if not master.is_dir():
        print("Path must be a directory: ", master); sys.exit(1)

    organizer = ScanOrganizer()
    organizer.load_master(master)
    organizer.display()
