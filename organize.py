#!/usr/bin/env python3

# Phase 1 [-cleaned]: Clean up pictures. +cleaned
# Phase 2 [-categorized]: Categorize pictures (sort into folders). +categorized
# Phase 3 [-named +categorized]: Name files. +named
# Phase 4 [-hand_transcribe -computer_transcribe -no_text]: Tag files as needing transcription.
# Phase 5 [+hand_transcribe -transcribed]: Transcribe files by hand. +transcribed

import ui
import frontmatter, functools, natsort, os, pathlib, subprocess, sys

class OrganizerCategory():
    def __init__(self, path, parent):
        self.path = path
        self.parent = parent
    def relative_path(self):
        return self.path.relative_to(parent)

class OrganizerImage():
    def __init__(self, path, parent, categories):
        self.image_path = path
        self.parent = parent
        self.transcription_path = self._transcription_path(self.image_path)
        if self.transcription_path.exists():
            self.textfm = frontmatter.load(self.transcription_path)
        else:
            self.textfm = frontmatter.Post("")
            self.textfm['tags'] = []
        self.category = None
        for category in categories:
            if str(self.image_path).startswith(str(category.path)):
                if self.category is None or len(category.path) > len(self.category.path):
                    self.category = category
    def rename(self, new_name):
        self._move(self.image_path.parent.joinpath(new_name))
    def set_category(self, category):
        self.category = category
        self._move(category.path.joinpath(self.image_path.name))
    @property
    def transcription(self):
        return self.textfm.content
    @transcription.setter
    def transcription(self, content):
        self.textfm.content = content
        self._save_text()
    @property
    def tags(self):
        return self.textfm['tags']
    def tag(self, tag):
        """Add or remove a single tag"""
        assert any(tag.startswith(x) for x in "+-")
        symbol, tag = tag[:1], tag[1:]
        if symbol == "+":
            if tag not in self.tags:
                self.tags.append(tag)
        elif symbol == "-":
            if tag in self.tags:
                self.tags.remove(tag)
        self._save_text()
    def match_tags(self, tags):
        """Returns true if ALL tags are matched"""
        for tag in tags:
            if tag.startswith("+"):
                if tag[1:] not in self.tags:
                    return False
            elif tag.startswith("-"):
                if tag[1:] in self.tags:
                    return False
            else:
                assert False
        return True

    def _save_text(self):
        self.textfm['filename'] = self.image_path.name
        if self.category is not None:
            self.textfm['category'] = self.category.relative_path
        frontmatter.dump(self.textfm, self.transcription_path)
    def _move(self, new_path):
        old_image_path, self.image_path = self.image_path, new_path
        old_transcription_path, self.transcription_path = self.transcription_path, self._transcription_path(self.image_path)

        os.rename(old_image_path, self.image_path)
        #if old_transcription_path.exists():
        os.rename(old_transcription_path, self.transcription_path)
    def _transcription_path(self, image_path):
        return image_path.parent.joinpath(image_path.stem + ".txt")

class Organizer():
    def __init__(self):
        self.window = ui.TranscriptionWindow()
        self.images = []
        self.categories = []
        self.phase_images = {}
        self.phase_work_images = {}
        self.phase_tags = {}
        self.phase_index = {}

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
            #print(p)
            assert p.is_dir()
            for x in p.iterdir():
                #print(x)
                if x.is_file():
                    files.append(x)
                elif x.is_dir():
                    dirs.append(x)
        files = [f for f in files if f.suffix in {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".gif"}]
        categories = [d.relative_to(master) for d in dirs]

        for category in categories:
            organizer.add_category(category, master)
        for file in files:
            organizer.add_image(file, master)
        organizer.autoselect_phase()
    def add_phase(self, tags, **kwargs):
        phase = self.window.add_phase(**kwargs)
        self.phase_tags[phase] = tags
        self.phase_index[phase] = 0
        self.phase_images[phase] = [] # All of them added from the beginning
        self.phase_work_images[phase] = [] # The ones remaining that need work only, as indexes
        # Images are always added after phases, so skip any stuff to add them here.
    def add_image(self, image_path, parent):
        image = OrganizerImage(image_path, parent, self.categories)
        self.images.append(image)

        for phase, tags in self.phase_tags.items():
            if image.match_tags(tags):
                self.phase_images[phase].append(image)
                self.phase_work_images[phase].append(len(self.phase_images[phase])-1)
                phase.increment_todo(1)
                if self.phase_index[phase] == 0 and len(self.phase_images[phase]) == 1: # First image
                    self._update_image(phase)
            else:
                phase.increment_skipped(1)
    def add_category(self, category_path, parent):
        category = OrganizerCategory(category_path, parent)
        self.categories.append(category)
    def display(self):
        self.window.mainloop()
    def autoselect_phase(self):
        best_phase = None
        for phase, items in reversed(self.phase_work_images.items()):
            if len(items) == 0:
                phase.set_done(True)
            else:
                best_phase = phase
        if best_phase is not None:
            self.window.select_phase(best_phase)
    def _switch_index(self, phase, offset):
        current_index = self.phase_index[phase]

        if len(self.phase_images[phase]) == 0:
            new_index = 0
        else:
            new_index = (current_index + offset) % len(self.phase_images[phase])

        self.phase_index[phase] = new_index
        self._update_image(phase)
    def _switch_work_index(self, phase, offset, working_set):
        current_index = self.phase_index[phase]
        if len(working_set) == 0:
            new_index = 0
        else:
            # Next WORK image. Assumes we're on one. Should fix that, eventually
            assert current_index in working_set
            work_index = working_set.index(current_index)
            next_work_index = (work_index + offset) % len(working_set)
            new_index = working_set[next_work_index]

        self.phase_index[phase] = new_index
        self._update_image(phase)
    def _update_image(self, phase):
        index = self.phase_index[phase]
        if len(self.phase_images[phase]) == 0:
            phase.set_done(True)
            phase.set_image(None, False)
        else:
            phase.set_done(False)
            assert 0 <= index < len(self.phase_images[phase])
            image = self.phase_images[phase][index]
            is_work = index in self.phase_work_images[phase]
            phase.set_image(image, is_work)
    def _reload_image(self, image):
        """Use if we think an image was changed externally"""
        for phase, index in self.phase_index.items():
            if len(self.phase_images[phase]) > 0 and self.phase_images[phase][index] == image:
                is_work = index in self.phase_work_images[phase]
                phase.set_image(image, is_work)
    def _run(self, command):
        done = subprocess.run(command)
        return done.returncode == 0

    # Button actions
    def next(self, phase, image):
        print("next")
        return self._switch_index(phase, 1)
    def prev(self, phase, image):
        print("prev")
        return self._switch_index(phase, -1)
    def next_work(self, phase, image):
        print("next_work")
        return self._switch_work_index(phase, 1, self.phase_work_images[phase])
    def prev_work(self, phase, image):
        print("prev_work")
        return self._switch_work_index(phase, -1, self.phase_work_images[phase])
    def tag(self, tag, phase, image):
        print("tag", tag)
        before = { phase: image.match_tags(tags) for phase, tags in self.phase_tags.items() }
        before_index = { phase: self.phase_images[phase].index(image) for phase, truth in before.items() if truth == True }
        image.tag(tag)
        after  = { phase: image.match_tags(tags) for phase, tags in self.phase_tags.items() }
        for phase in self.phase_tags:
            if after[phase] == True and before[phase] == False:
                # Added to phase
                index = self.phase_images[phase].index(image)
                self.phase_work_images.append()
                phase.increment_todo(1)
                phase.increment_skipped(-1) # Usually it's skipped and not finished, but this is a guess
                if len(self.phase_work_images) == 1: # New first image
                    self._update_image(phase)
                    phase.set_done(False)
            elif before[phase] == True and after[phase] == False:
                # Removed from phase.
                index = before_index[phase]
                phase.increment_todo(-1)
                phase.increment_finished(1)
                if self.phase_index[phase] == index: # advance the cursor, too
                    self.next_work(phase, image)
                self.phase_work_images[phase].remove(index)
                if len(self.phase_work_images[phase]) == 0:
                    self.autoselect_phase()
                    phase.set_done(True, popup=True)
    def rotate_left(self, _, image):
        print("rotate_left")
        self._run(["convert", image.image_path, "-rotate", "270", image.image_path])
        self._reload_image(image)
    def rotate_right(self, _, image):
        print("rotate_right")
        self._run(["convert", image.image_path, "-rotate", "90", image.image_path])
        self._reload_image(image)
    def crop(self, _, image):
        print("crop")
        success = self._run(["cropgui", image.image_path]) # Only works on jpg
        if success:
            new_path = image.image_path.parent.joinpath("{}-crop{}".format(image.image_path.stem, image.image_path.suffix))
            os.rename(new_path, image.image_path)
            self._reload_image(image)
    def set_category(self, phase, image):
        print("set_category")
        category = phase.get_category()
        image.set_category(category)
    def set_name(self, phase, image):
        print("set_name")
        name = phase.get_name()
        image.rename(name)
    def save_transcription(self, phase, image):
        print("save_transcription")
        image.transcription = phase.get_transcription()

if __name__ == "__main__":
    if len(sys.argv) == 1:
        master = pathlib.Path(os.getcwd())
    elif len(sys.argv) == 2:
        master = pathlib.Path(sys.argv[1])
    else:
        print("Too many paths"); sys.exit(1)
    if not master.is_dir():
        print("Path must be a directory: ", master); sys.exit(1)

    organizer = Organizer()
    organizer.load_master(master)
    organizer.display()
