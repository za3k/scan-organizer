#!/usr/bin/env python3
import collections
import enum
import functools
import os.path
import re

import natsort
import PIL
import PIL.Image
import PIL.ImageTk
import tkinter as tk
import tkinter.messagebox as tkmessagebox
import tkinter.ttk as ttk


class ButtonActionInvalidError(BaseException):
    def __init__(self, reason):
        self.message = reason


class Extras(enum.Enum):
    CATEGORY_PICKER = "category_picker"
    METADATA_DISPLAY = "metadata_display"
    RENAME = "rename"
    SHOW_CATEGORY = "show_category"
    TRANSCRIBE = "transcribe"


class EventHaver():
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._handlers = collections.defaultdict(list)
    def on(self, event, handler):
        self._handlers[event].append(handler)
    def event(self, event, *args, **kwargs):
        for handler in self._handlers[event]:
            handler(*args, **kwargs)


class Ignorer():
    def __init__(self):
        pass
    def __getattr__(self, name):
        return self
    def __call__(self, *args, **kwargs):
        pass


class Image(tk.Canvas):
    def __init__(self, parent):
        super().__init__(parent)
        self.img = None
        self.bind("<Configure>", self.resize)

    def set(self, image_path):
        if image_path is None:
            self.img = None 
        else:
            self.img = PIL.Image.open(image_path)
        self.update_image(self.img)
    
    def update_image(self, img, width=None, height=None):
        if width is None:
            width, height = self.winfo_width(), self.winfo_height()
        if img is None:
            self.delete("all")
            return

        # Keep aspect ratio
        img_width, img_height = img.size
        ratio = min(width*1.0/img_width, height*1.0/img_height)
        width, height = max(int(img_width*ratio),1), max(int(img_height*ratio),1)

        self.pi = PIL.ImageTk.PhotoImage(img.resize(
            (width, height), PIL.Image.Resampling.LANCZOS
        ))
        self.delete("all")
        self.create_image(0, 0, anchor=tk.NW, image=self.pi) 

    def resize(self, event):
        self.update_image(self.img, width=event.width, height=event.height)


class TranscriptionWindow(tk.Tk):
    def __init__(self, *args, **kw_args): 
        super().__init__(*args, **kw_args)

        self.phases = []
        self.tabControl = ttk.Notebook(self)
        self.tabControl.pack(expand=1, fill="both")
        self.tabControl.enable_traversal() # Keyboard shortcuts like Control-Tab
        self.tabControl.bind("<<NotebookTabChanged>>", self.on_tab_change)
        self.bind_all("<Key>", self.handle_keypress)

    def add_phase(self, name, **kw_args):
        shortcut_index = -1
        if "^" in name:
            shortcut_index = name.index("^")
            name = name.replace("^", "")
        phase = TranscriptionPhase(self.tabControl, name=name, **kw_args)
        self.tabControl.add(phase, text=name, underline=shortcut_index)
        self.phases.append(phase)
        return phase
    
    def select_phase(self, phase):
        index = self.tabControl.tabs().index(str(phase))
        self.tabControl.select(index)

    def on_tab_change(self, event):
        active_tab = self.tabControl.index("current")
        phase = self.phases[active_tab]
        phase.focus_set()
        phase.refresh()

    def handle_keypress(self, event):
        excluded = (ExtraTranscribe, tk.Entry,)
        active_tab = self.tabControl.index("current")
        phase = self.phases[active_tab]
        if isinstance(event.widget, excluded) and event.state == 0:
            return
        return phase.handle_keypress(event)

    @property
    def active(self):
        notebook = self.master
        return notebook.tab(notebook.index("current"), "text") == self.id
        if not self.active:
            return
        if any(isinstance(event.widget, widget_type) for widget_type in excluded):
            return
        return self._handle_button(actions, event)


class TranscriptionPhase(tk.Frame):
    def __init__(self, root, name, extras, buttons, get_categories=None):
        super().__init__(root)
        self.id = name
        self.image = None
        self.todo = 0
        self.finished = 0
        self.skipped = 0
        self.current_image = None

        # self.photo_frame      self.extras_frame
        # +-------------------+ +-----------------------------+
        # |    label          | |                             |
        # +-------------------| |                             |
        # |    label          | |                             |
        # +-------------------| |         extras              |
        # |                   | |                             |
        # |    image_canvas   | |                             |
        # |                   | |                             |
        # +-------------------+ +-----------------------------+
        # +---------------------------------------------------+
        # | save | left | right | crop | prev | next          |
        # +---------------------------------------------------+
        # self.buttons_frame

        # Variables
        self.sv_current_image_path = tk.StringVar(self, "Loading...")
        self.sv_current_image_name = tk.StringVar(self, "Loading...")
        self.sv_progress = tk.StringVar(self, "Loading...")

        # "Flex" rows that take up extra space
        # self.frame layout
        # +---------------------+----------------+
        # |                     |                |
        # |  photo frame        |      extras    | Row 1
        # |                     |      frame     |
        # |                     |                |
        # +---------------------+----------------+
        # |           buttons frame              | Row 2
        # +--------------------------------------+
        self.grid(row=0, column=0, sticky=tk.W+tk.N+tk.E+tk.S)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(1, minsize=100)
        self.photo_frame = tk.Frame(self) # background="red" to show
        self.extras_frame = tk.Frame(self)
        self.buttons_frame = tk.Frame(self)
        self.photo_frame.grid(column=1, row=1, sticky=tk.W+tk.N+tk.N+tk.S+tk.E)
        self.extras_frame.grid(column=2, row=1, sticky=tk.W+tk.N+tk.S+tk.E)
        self.buttons_frame.grid(column=1, row=2, columnspan=2, sticky=tk.W+tk.E+tk.S)


        # self.photo_frame layout
        # +-------------------+
        # |    label          |
        # +-------------------|
        # |    label          |
        # +-------------------|
        # |                   |
        # |    image_canvas   |
        # |                   |
        # +-------------------+
        self.photo_frame.grid_columnconfigure(1, weight=1) # allocate extra space to row 3 and column 1
        self.photo_frame.grid_rowconfigure(3, weight=1)
        self.lbl_image = tk.Label(self.photo_frame, textvariable=self.sv_current_image_path, padx=20, pady=0)
        self.lbl_image.grid(column=1, row=1)
        self.lbl_progress = tk.Label(self.photo_frame, textvariable=self.sv_progress, padx=20, pady=0)
        self.lbl_progress.grid(column=1, row=2)
        self.image_canvas = Image(self.photo_frame)
        self.image_canvas.grid(column=1, row=3, rowspan=2, sticky=tk.W+tk.N+tk.E+tk.S)

        # self.extras_frame
        self.extras = {}
        self.extras_frame.grid_rowconfigure(1, weight=1)
        for i, extra_request in enumerate(extras):
            if extra_request == Extras.CATEGORY_PICKER:
                extra = ExtraCategoryPicker(self.extras_frame, get_categories=get_categories)
            elif extra_request == Extras.METADATA_DISPLAY:
                extra = ExtraMetadataDisplay(self.extras_frame)
            elif extra_request == Extras.SHOW_CATEGORY:
                extra = ExtraShowCategory(self.extras_frame)
            elif extra_request == Extras.RENAME:
                extra = ExtraRename(self.extras_frame)
            elif extra_request == Extras.TRANSCRIBE:
                extra = ExtraTranscribe(self.extras_frame)
            else:
                assert False
            self.extras[extra_request] = extra
            #self.extras_frame.grid_columnconfigure(i, weight=1)
            extra.grid(column=i, row=1, sticky=extra.get_sticky())
        #self.get_extra(Extras.RENAME).set_name(filename)
        self.get_extra(Extras.SHOW_CATEGORY).on("click_file", self.on_click_file)
            
        # +---------------------------------------------------+
        # | save | left | right | crop | prev | next          |
        # +---------------------------------------------------+
        # self.buttons_frame
        self.shortcuts = {}
        for i, (label, actions) in enumerate(buttons.items()):
            m = re.fullmatch(r'[^()]+ \(([^()]+)\)', label)
            shortcut_index = -1
            if m:
                shortcut_index = m.start(1)
                shortcuts = m.group(1)
                for shortcut in shortcuts.split("/"):
                    state, key = {
                        "←": (0, "Left"),
                        "→": (0, "Right"),
                        "<": (1, "less"),
                        ">": (1, "greater"),
                        # Regular Enter key only.
                        "⏎": (0, "Return"),
                        " ": (0, "space"),
                        # Shift-enter. Note, this still ends up adding a blank line in the transcription box
                        "⇧⏎": (1, "Return"),
                        "del": (0, "Delete"),
                        "C-n": (4, "n"),
                    }.get(shortcut, (None, shortcut))
                    self.shortcuts[(state, key)] = actions
            button = tk.Button(self.buttons_frame, text=label, underline=shortcut_index)
            button.grid(column=i, row=1)
            button.bind("<Button-1>", functools.partial(self._handle_button, actions))
        #self.bind_all("<Key>", lambda event: print(event.keysym, event, event.state))

    def on_click_file(self, filename):
        self.get_extra(Extras.RENAME).set_name(os.path.splitext(filename)[0])

    def handle_keypress(self, event):
        state, key = event.state, event.keysym
        actions = self.shortcuts.get((None, key))
        actions = self.shortcuts.get((state, key), actions)
        if actions is not None:
            self._handle_button(actions, event)

    def _handle_button(self, actions, event):
        if not isinstance(actions, list):
            actions = [actions]
        for action in actions:
            try:
                action(self, self.current_image)
            except ButtonActionInvalidError as e:
                tkmessagebox.showinfo(message=e.message)
                return
    
    def refresh(self):
        if self.current_image is not None:
            self.set_image(*self._refresh_args)

    def __hash__(self):
        return hash(self.id)

    def get_extra(self, e):
        return self.extras.get(e, Ignorer()) # Magic so we don't have to check for None

    def set_image(self, image, is_work, categories, recent_categories):
        self.current_image = image
        self._refresh_args = (image, is_work, categories, recent_categories)
        if self.current_image is None:
            self.sv_current_image_path.set("Complete")
            self.sv_current_image_name.set("Complete")
            self.image_canvas.set(None)
            self.get_extra(Extras.CATEGORY_PICKER).set_category(None, categories, recent_categories, False)
            self.get_extra(Extras.METADATA_DISPLAY).set_metadata("")
            self.get_extra(Extras.RENAME).set_name("")
            self.get_extra(Extras.SHOW_CATEGORY).set_category(None)
            self.get_extra(Extras.TRANSCRIBE).set_transcription("")
        else:
            self.image_canvas.set(self.current_image.image_path)
            self.sv_current_image_path.set(str(self.current_image.image_path))
            self.sv_current_image_name.set(self.current_image.image_path)
            self.get_extra(Extras.CATEGORY_PICKER).set_category(image.category, categories, recent_categories, image.category is not None)
            self.get_extra(Extras.METADATA_DISPLAY).set_metadata(image.metadata_string)
            self.get_extra(Extras.RENAME).set_name(image.image_path.stem)
            self.get_extra(Extras.SHOW_CATEGORY).set_category(image.category)
            self.get_extra(Extras.TRANSCRIBE).set_transcription(image.transcription)

    def increment_todo(self, amount=1):
        self.todo += amount
        self.update_progress()

    def increment_skipped(self, amount=1):
        self.skipped += amount
        self.update_progress()
            
    def increment_finished(self, amount=1):
        self.finished += amount
        self.update_progress()

    def set_done(self, done, popup=False):
        if done:
            self.set_image(None, False, [], [])
            if popup:
                tkmessagebox.showinfo(message="{} complete".format(self.id))

    def update_progress(self):
        if self.todo + self.finished == 0:
            done = 1
        else:
            done = self.finished / (self.todo + self.finished)
        self.sv_progress.set("{}% done | {} complete | {} incomplete | {} skipped".format(int(done*100), self.finished, self.todo, self.skipped))


class Extra():
    def get_sticky(self):
        return tk.W+tk.N+tk.E+tk.S


class ExtraCategoryPicker(tk.Frame, Extra, EventHaver):
    """Category picker.

    Displays a list of possible categories, and allows selecting one.
    Allows making a new category.
    If a category is selected, displays information about that category.

    Does not save choice automatically.
    """
    def __init__(self, root, get_categories):
        tk.Frame.__init__(self, root)
        EventHaver.__init__(self)

        self.SHORTCUTS = "1234567890"
        self.choices = tk.StringVar(value=[])
        self.filenames = tk.StringVar(value=[])
        self.sv_new_category = tk.StringVar(value="")
        self._categories = []

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.listbox = tk.Listbox(self, listvariable=self.choices)
        self.listbox.grid(column=1, row=1, columnspan=2, sticky=tk.W+tk.N+tk.E+tk.S)
        self.listbox2 = tk.Listbox(self, listvariable=self.filenames, state=tk.DISABLED)
        self.listbox2.grid(column=3, row=1, sticky=tk.W+tk.N+tk.E+tk.S)
        self.listbox.bind("<<ListboxSelect>>", self.on_selection_change)
        self.category_name = tk.Entry(self, textvariable=self.sv_new_category)
        self.category_name.grid(column=1, row=2)
        self.add_category_button = tk.Button(self, text="Add New")
        self.add_category_button.grid(column=2, row=2)
        self.add_category_button.bind("<Button-1>", self.on_create_category)
        self.rename_category_button = tk.Button(self, text="Rename")
        self.rename_category_button.grid(column=3, row=2)
        self.rename_category_button.bind("<Button-1>", self.on_rename_category)
        for key in self.SHORTCUTS:
            self.listbox.bind(key, self.on_keystroke)

    def on_keystroke(self, event):
        state, key = event.state, event.keysym
        if state != 0:
            return
        if key not in self.shortcuts:
            return
        category = self.shortcuts[key]
        self.set_category(category, self._categories, self._recent_categories)
        self.listbox.xview_moveto(0)

    def set_category(self, active_category, categories, recent_categories, show=True):
        self._recent_categories = [x for x in recent_categories]
        _categories = natsort.natsorted([(category not in self._recent_categories, category.name, category) for category in categories])
        self.shortcuts = {}
        self._categories = []
        choices = []
        for i, (not_recent, category_name, category) in enumerate(_categories):
            is_recent = not not_recent
            self._categories.append(category)
            if is_recent:
                self.shortcuts[self.SHORTCUTS[i]] = category
                choices.append("({}) {}".format(self.SHORTCUTS[i], category_name))
            else:
                choices.append(category_name)
        self.choices.set(choices)

        self.listbox.select_clear(0, "end")
        if active_category is not None:
            index = self._categories.index(active_category)
            self.listbox.selection_set((index,))
            if show:
                self.listbox.see(index)
        self.on_category_changed()

    def get_category(self):
        if len(self.listbox.curselection()) == 1:
            index = self.listbox.curselection()[0]
            return self._categories[index]

    def on_selection_change(self, event):
        self.on_category_changed()

    def on_category_changed(self):
        self.listbox2.select_clear(0, "end")
        selected_category = self.selected_category
        # If the category is unset, don't reset the textbox
        if selected_category is not None:
            self._last_selected_category = selected_category
            filenames = [file.name for file in selected_category.path.iterdir() if file.suffix != ".txt"]
            self.filenames.set(natsort.natsorted(filenames))
            self.sv_new_category.set(selected_category.name)

    @property
    def selected_category(self):
        if len(self.listbox.curselection()) == 1:
            selected_index, = self.listbox.curselection()
            return self._categories[selected_index]

    def on_create_category(self, event):
        category_name = self.sv_new_category.get().strip()
        if category_name == "":
            tkmessagebox.showinfo(message="You must type a category name")
            return
        try:
            self.event("create_category", category_name)
            self.set_category(*self.get_categories(category_name))
        except ButtonActionInvalidError as e:
            tkmessagebox.showinfo(message=e.message)

    def on_rename_category(self, event):
        category_old = self._last_selected_category
        new_category_name = self.sv_new_category.get().strip()
        if new_category_name == "":
            tkmessagebox.showinfo(message="You must type a category name")
            return
        elif category_old.name == new_category_name == "":
            tkmessagebox.showinfo(message="You must change the category name")
            return
        try:
            self.event("rename_category", category_old, new_category_name)
            self.set_category(*self.get_categories(new_category_name))
        except ButtonActionInvalidError as e:
            tkmessagebox.showinfo(message=e.message)


class ExtraMetadataDisplay(tk.Text, Extra):
    """Display the metadata for the current image without allowing editing"""
    def __init__(self, root):
        super().__init__(root, bg="lightgrey")
        self.config(state=tk.DISABLED)

    def set_metadata(self, text):
        self.config(state=tk.NORMAL)
        self.delete("1.0", tk.END)
        self.insert("1.0", text)
        self.config(state=tk.DISABLED)


class ExtraShowCategory(tk.Frame, Extra, EventHaver):
    """Display the current category and files in it"""
    def __init__(self, root):
        super().__init__(root)
        EventHaver.__init__(self)
        self.rowconfigure(2, weight=1)
        self.filenames = tk.StringVar(value=[])
        self.sv_category = tk.StringVar(value="Loading...")
        self.label = tk.Label(self, textvariable=self.sv_category)
        self.listbox = tk.Listbox(self, listvariable=self.filenames)#, state=tk.DISABLED)
        self.label.grid(column=1, row=1, sticky=tk.W+tk.E)
        self.listbox.grid(column=1, row=2, sticky=tk.W+tk.N+tk.E+tk.S)
        self.listbox.bind("<<ListboxSelect>>", self.click_file)

    def set_category(self, category):
        self.sv_category.set(category.name if category is not None else "")

        self.listbox.select_clear(0, "end")
        if category is not None:
            filenames = [file.name for file in category.path.iterdir() if file.suffix != ".txt"]
            self.filenames.set(natsort.natsorted(filenames))

    def click_file(self, event):
        selected_index, = self.listbox.curselection()
        filename = self.listbox.get(selected_index)
        self.event("click_file", filename)


class ExtraRename(tk.Frame, Extra):
    """Image rename text box

    Loaded with existing name to start.

    Does not save new name automatically.
    """
    def __init__(self, root):
        super().__init__(root)

        self.label = tk.Label(self, text="Filename")
        self.textbox = tk.Entry(self)

        # Center the label and textbox without stretching them vertically
        self.grid_rowconfigure(1, weight=1)
        #self.grid_rowconfigure(4, weight=1) # Wait actually put them on the bottom
        self.label.grid(column=1, row=2, sticky=tk.W+tk.E)
        self.textbox.grid(column=1, row=3, sticky=tk.W+tk.E)

    def set_name(self, name):
        self.textbox.delete(0, tk.END)
        self.textbox.insert(0, name)

    def get_name(self):
        return self.textbox.get()


class ExtraTranscribe(tk.Text, Extra):
    """Transcription window

    Loaded with any existing transcription.

    Does not save transcribed content automatically.
    """
    def __init__(self, root):
        super().__init__(root)

    def set_transcription(self, transcription):
        self.delete("1.0", tk.END)
        self.insert("1.0", transcription)

    def get_transcription(self):
        return self.get("1.0", tk.END)
