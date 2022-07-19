#!/usr/bin/env python3
#TODO: Buttons to finish should maybe be greyed out if you can't do it
import enum
import functools

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

        self.tabControl = ttk.Notebook(self)
        self.tabControl.pack(expand=1, fill="both")

    def add_phase(self, name, **kw_args):
        phase = TranscriptionPhase(self.tabControl, name=name, **kw_args)
        self.tabControl.add(phase, text=name)
        return phase
    
    def select_phase(self, phase):
        index = self.tabControl.tabs().index(str(phase))
        self.tabControl.select(index)


class TranscriptionPhase(tk.Frame):
    def __init__(self, root, name, extras, buttons):
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
                extra = ExtraCategoryPicker(self.extras_frame)
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
            
        # +---------------------------------------------------+
        # | save | left | right | crop | prev | next          |
        # +---------------------------------------------------+
        # self.buttons_frame
        for i, (label, actions) in enumerate(buttons.items()):
            button = tk.Button(self.buttons_frame, text=label)
            button.grid(column=i, row=1)
            button.bind("<Button-1>", functools.partial(self._handle_button, actions))

    def _handle_button(self, actions, event):
        if not isinstance(actions, list):
            actions = [actions]
        for action in actions:
            try:
                action(self, self.current_image)
            except ButtonActionInvalidError as e:
                print("cancelling action because: {}".format(e.message))
                return

    def __hash__(self):
        return hash(self.id)

    def get_extra(self, e):
        return self.extras.get(e, Ignorer()) # Magic so we don't have to check for None

    def set_image(self, image, is_work, categories):
        self.current_image = image
        if self.current_image is None:
            self.sv_current_image_path.set("Complete")
            self.sv_current_image_name.set("Complete")
            self.image_canvas.set(None)
            self.get_extra(Extras.CATEGORY_PICKER).set_category(None, categories)
            self.get_extra(Extras.METADATA_DISPLAY).set_metadata("")
            self.get_extra(Extras.RENAME).set_name("")
            self.get_extra(Extras.SHOW_CATEGORY).set_category(None)
            self.get_extra(Extras.TRANSCRIBE).set_transcription("")
        else:
            self.image_canvas.set(self.current_image.image_path)
            self.sv_current_image_path.set(str(self.current_image.image_path))
            self.sv_current_image_name.set(self.current_image.image_path.name)
            self.get_extra(Extras.CATEGORY_PICKER).set_category(image.category, categories)
            self.get_extra(Extras.METADATA_DISPLAY).set_metadata(image.metadata_string)
            self.get_extra(Extras.RENAME).set_name(image.image_path.name)
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
            self.set_image(None, False, [])
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

class ExtraCategoryPicker(tk.Frame, Extra):
    """Category picker.

    Displays a list of possible categories, and allows selecting one.
    Allows making a new category.
    TODO (move to show category): If a category is selected, displays information about that category.

    Does not save choice automatically.
    """
    # TODO: Show contents of category and preview of those files
    # TODO: Allow adding categories
    def __init__(self, root):
        super().__init__(root)

        self.choices = tk.StringVar(value=[])

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.listbox = tk.Listbox(self, listvariable=self.choices)
        self.listbox.grid(column=1, row=1)

    def set_category(self, category, categories):
        self.choices.set([category.name for category in categories])

    def get_category_name(self):
        if len(self.listbox.curselection()) == 1:
            return self.listbox.get(self.listbox.curselection())

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


# TODO
class ExtraShowCategory(tk.Frame, Extra):
    """Display the current category and files in it"""
    def __init__(self, root):
        super().__init__(root)
        #self.category_menu = tk.OptionMenu(self.transcription_frame, value="A", variable=self.sv_category_name)
        #self.category_menu.grid(column=2, row=1)

    def set_category(self, category):
        pass


class ExtraRename(tk.Entry, Extra):
    """Image rename text box

    Loaded with existing name to start.

    Does not save new name automatically.
    """
    def __init__(self, root):
        super().__init__(root)

    def get_sticky(self):
        return tk.W+tk.E

    def set_name(self, name):
        self.delete(0, tk.END)
        self.insert(0, name)

    def get_name(self):
        return self.get()


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
