#!/usr/bin/env python3
import collections
import functools
import os

import frontmatter

import ui
from ui import Extras


class SaveInvalidError(ui.ButtonActionInvalidError):
    pass


class ImageClobberingError(ui.ButtonActionInvalidError):
    def __init__(self):
        super().__init__("Image already exists")


class OrganizerCategory():
    def __init__(self, path, name):
        self.path = path
        self.name = name


class OrganizerImage():
    def __init__(self, path, category, index):
        self.image_path = path
        self.transcription_path = self._transcription_path(self.image_path)
        self.index = index # an id
        self.category = category
        if self.transcription_path.exists():
            self.textfm = frontmatter.load(self.transcription_path)
        else:
            self.textfm = frontmatter.Post("")
            self.textfm['tags'] = []

    def rename(self, new_name):
        self._move(self.image_path.parent.joinpath(new_name))

    def set_category(self, category):
        self.category = category
        self._move(category.path.joinpath(self.image_path.name))

    @property
    def metadata_string(self):
        return frontmatter.dumps(self.textfm)

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
        if symbol == "+" and tag not in self.tags:
            self.tags.append(tag)
        elif symbol == "-" and tag in self.tags:
            self.tags.remove(tag)
        self._save_text()

    def match_tags(self, tags):
        """Returns true if ALL tags are matched"""
        for tag in tags:
            assert any(tag.startswith(x) for x in "+-")
            symbol, tag = tag[:1], tag[1:]
            if symbol == "+" and tag not in self.tags:
                return False
            elif symbol == "-" and tag in self.tags:
                return False
        return True

    def _save_text(self):
        self.textfm['filename'] = self.image_path.name
        if self.category is not None:
            self.textfm['category'] = self.category.name
        frontmatter.dump(self.textfm, self.transcription_path)

    def _move(self, new_path):
        if new_path == self.image_path:
            return
        if new_path.exists():
            raise ImageClobberingError()
        old_image_path, self.image_path = self.image_path, new_path
        old_transcription_path, self.transcription_path = self.transcription_path, self._transcription_path(self.image_path)

        os.rename(old_image_path, self.image_path)
        if old_transcription_path.exists():
            os.rename(old_transcription_path, self.transcription_path)

    def _transcription_path(self, image_path):
        return image_path.parent.joinpath(image_path.stem + ".txt")

class Organizer():
    def __init__(self, new_category_root):
        self.window = ui.TranscriptionWindow()
        self.new_category_root = new_category_root
        self.images = []
        self.categories = []
        self._phases = []
        # phase -> All images for that phase, at least those unfinished at the program start. As indices
        self._phase_images = collections.defaultdict(list)
        # phase -> Images still requiring work. As indices
        self._phase_work_images = collections.defaultdict(list)
        # phase -> list of tags
        self._phase_tags = {}
        # phase -> current selected image
        self._phase_index = collections.defaultdict(lambda: None)

    def add_phase(self, tags, **kwargs):
        phase = self.window.add_phase(on_create_category=self.on_create_category, **kwargs)
        self._phases.append(phase)
        self._phase_tags[phase] = tags
        # Images are always added after phases, so skip iterating over existing images

    def set_phase_index(self, phase, index):
        self._phase_index[phase] = index

    def phase_info(self, phase):
        return self._phase_tags[phase], self._phase_index[phase], self._phase_images[phase], self._phase_work_images[phase]

    def phases(self):
        for phase in self._phases:
            yield phase, *self.phase_info(phase)

    def add_image(self, image_path):
        image = OrganizerImage(image_path, self._find_category(image_path), index=len(self.images))
        self.images.append(image)

        for phase, tags, phase_index, images, work_images in self.phases():
            if image.match_tags(tags):
                images.append(image.index)
                work_images.append(image.index)
                phase.increment_todo(1)
                if phase_index is None:
                    self.set_image(phase, image.index)
            else:
                phase.increment_skipped(1)

    def add_category(self, category_path, category_name):
        category = OrganizerCategory(category_path, category_name)
        self.categories.append(category)

    def display(self):
        self.window.mainloop()

    def autoselect_phase(self):
        best_phase = None
        for phase, _, _, _, work_images in reversed(list(self.phases())):
            if len(work_images) > 0:
                best_phase = phase
        if best_phase is not None:
            self.window.select_phase(best_phase)

    def set_image(self, phase, new_index):
        """Use if the selected image changed for a phase"""
        self.set_phase_index(phase, new_index)
        tags, phase_index, images, work_images = self.phase_info(phase)
        if len(images) == 0 or new_index is None:
            assert new_index is None
            phase.set_image(None, False, [])
            phase.set_done(True)
        else:
            assert new_index is not None
            phase.set_done(False)
            assert phase_index in images
            image = self.images[phase_index]
            phase.set_image(
                image,
                is_work=phase_index in work_images,
                categories=self.categories,
            )

    def reload_image(self, image):
        """Use if we think an image was changed externally"""
        for phase, tags, phase_index, images, work_images in self.phases():
            if len(images) > 0 and phase_index == image.index:
                phase.set_image(image, phase_index in work_images)

    def _switch_index(self, phase, offset, working_set):
        _, current_index, _, _ = self.phase_info(phase)
        if len(working_set) == 0:
            new_index = None
        else:
            # Next image. Assumes we're on one. Should fix that, eventually
            assert current_index in working_set
            work_index = working_set.index(current_index)
            next_work_index = (work_index + offset) % len(working_set)
            new_index = working_set[next_work_index]

        self.set_image(phase, new_index)

    def _find_category(self, image_path):
        """Figure out the (narrowest) category an image is in"""
        correct_category = None
        for category in self.categories:
            if str(image_path).startswith(str(category.path)):
                if correct_category is None or len(str(category.path)) > len(str(correct_category.path)):
                    correct_category = category
        return correct_category

    def on_create_category(self, category_name):
        category_path = self.new_category_root.joinpath(category_name)
        category = OrganizerCategory(category_path, category_name)
        try:
            os.makedirs(category_path)
        except FileExistsError:
            raise ui.ButtonActionInvalidError("That category already exists")
        self.categories.append(category)
        return category, self.categories


    # Common (model-level) buttons
    def next(self, phase, image):
        _, _, images, _ = self.phase_info(phase)
        return self._switch_index(phase, 1, images)

    def prev(self, phase, image):
        _, _, images, _ = self.phase_info(phase)
        return self._switch_index(phase, -1, images)

    def next_work(self, phase, image):
        _, _, _, work_images = self.phase_info(phase)
        return self._switch_index(phase, 1, work_images)

    def prev_work(self, phase, image):
        _, _, _, work_images = self.phase_info(phase)
        return self._switch_index(phase, -1, work_images)

    def tag(self, tag): # A button's action should be self.tag("+some_tag")
        return lambda phase, image: self._tag(tag, phase, image) 

    def _tag(self, tag, phase, image):
        before = { phase: image.match_tags(tags) for phase, tags, _, _, _ in self.phases() }
        image.tag(tag)
        after  = { phase: image.match_tags(tags) for phase, tags, _, _, _ in self.phases() }
        for phase, tags, phase_index, images, work_images in self.phases():
            if before[phase] == False and after[phase] == True:
                # Added to phase
                assert image.index not in work_images
                if image.index not in work_images:
                    work_images.append(image.index)
                    phase.increment_todo(1)
                    if image.index not in images:
                        images.append(image.index)
                        phase.increment_skipped(-1)
                    else:
                        phase.increment_finished(-1)
                if len(work_images) == 1: # New first image
                    self.set_image(phase, image.index)
            elif before[phase] == True and after[phase] == False:
                # Removed from phase.
                phase.increment_todo(-1)
                phase.increment_finished(1)
                if phase_index == image.index: # advance the cursor, too
                    self.next_work(phase, image)
                work_images.remove(image.index)
                if len(work_images) == 0:
                    self.set_image(phase, None)
                    phase.set_done(True, popup=True)
                    self.autoselect_phase()


    # Default extras (UI-level) buttons
    def save_category(self, phase, image):
        category_name = phase.get_extra(Extras.CATEGORY_PICKER).get_category_name()
        if category_name is None:
            raise SaveInvalidError("Category not selected")
        category = [category for category in self.categories if category.name == category_name][0]
        image.set_category(category)

    def save_name(self, phase, image):
        name = phase.get_extra(Extras.RENAME).get_name()
        if name is None or name.strip() == "":
            raise SaveInvalidError("Enter a filename")
        image.rename(name)

    def save_transcription(self, phase, image):
        transcription = phase.get_extra(Extras.TRANSCRIBE).get_transcription()
        if transcription is None or transcription.strip() == "":
            raise SaveInvalidError("Transcription is empty")
        image.transcription = transcription
