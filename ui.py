#!/usr/bin/env python3
import functools, os, sys
import tkinter as tk
import tkinter.messagebox as tkmessagebox
import tkinter.ttk as ttk
from pathlib import Path
import natsort
import PIL, PIL.Image, PIL.ImageTk

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

        self.current_image = None
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

        # self.photo_frame      self.extras
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
        # |  photo frame        |  transcription | Row 1
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
        #self.transcription_frame.grid_columnconfigure(4, weight=1) # allocate extra space to row 2, column 4
        #self.transcription_frame.grid_rowconfigure(2, weight=1)
        #self.name_entry = tk.Entry(self.transcription_frame, textvariable=self.sv_current_image_name)
        #self.name_entry.grid(column=1, row=1)
        #self.category_menu = tk.OptionMenu(self.transcription_frame, value="A", variable=self.sv_category_name)
        #self.category_menu.grid(column=2, row=1)
        #self.btn_rename = tk.Button(self.transcription_frame, text="Rename")
        #self.btn_rename.grid(column=3, row=1)
        #self.txt_entry = tk.Text(self.transcription_frame)
        #self.txt_entry.grid(column=1, row=2, columnspan=4, sticky=tk.W+tk.N+tk.E+tk.S)

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
            action(self, self.current_image)
    def __hash__(self):
        return hash(self.id)
    def set_image(self, image, is_work):
        self.current_image = image
        if self.current_image is None:
            self.sv_current_image_path.set("Complete")
            self.sv_current_image_name.set("Complete")
            self.image_canvas.set(None)
        else:
            self.image_canvas.set(self.current_image.image_path)
            self.sv_current_image_path.set(str(self.current_image.image_path))
            self.sv_current_image_name.set(self.current_image.image_path.name)
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
            self.set_image(None, False)
            if popup:
                tkmessagebox.showinfo(message="{} complete".format(self.id))

    def update_progress(self):
        if self.todo + self.finished == 0:
            done = 1
        else:
            done = self.finished / (self.todo + self.finished)
        self.sv_progress.set("{}% done | {} complete | {} incomplete | {} skipped".format(int(done*100), self.finished, self.todo, self.skipped))
