import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import sv_ttk
from conversion import conversion_manager
from utils import extract_frame_with_conversion, extract_frame, TONEMAP, get_video_properties
from PIL import Image, ImageTk, ImageOps
from tkinterdnd2 import DND_FILES
import logging

DEFAULT_MIN_SIZE = (550, 150)

class HDRConverterGUI:
    """
    A class encapsulating the GUI components and functionality for the HDR to SDR Converter application.
    """

    def __init__(self, root):
        """Initialize the GUI and set up all components."""
        self.root = root
        self.root.title("HDR to SDR Converter")
        sv_ttk.set_theme("dark")
        self.root.minsize(*DEFAULT_MIN_SIZE)
        self.root.resizable(False, False)

        # Variables
        self.input_path_var = tk.StringVar()
        self.output_path_var = tk.StringVar()
        self.gamma_var = tk.DoubleVar(value=1.0)
        self.progress_var = tk.DoubleVar(value=0)
        self.open_after_conversion_var = tk.BooleanVar()
        self.display_image_var = tk.BooleanVar(value=True)
        self.original_image = None
        self.converted_image_base = None
        self.gpu_accel_var = tk.BooleanVar(value=False)
        self.filter_options = ['Static', 'Dynamic']
        self.filter_var = tk.StringVar(value=self.filter_options[1])
        self.tonemap_var = tk.StringVar(value='Mobius')
        self.tooltip = None
        self.current_frame_index = 1
        self.total_frames = 5
        self.last_time_position = None

        # Create widgets and configure layout
        self.create_widgets()
        self.configure_grid()

        # Bind events
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.handle_file_drop)
        self.drop_target_registered = True

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.cancelled = False

    def on_close(self):
        if conversion_manager.process and conversion_manager.process.poll() is None:
            if messagebox.askokcancel("Quit", "A conversion is in progress. Do you want to cancel and exit?"):
                conversion_manager.cancel_conversion(
                    self, self.interactable_elements, self.cancel_button
                )
                self.root.destroy()
        else:
            self.root.destroy()

    def create_widgets(self):
        # Control Frame (Row 0)
        self.control_frame = ttk.Frame(self.root, padding="10")
        self.control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N))

        # Input File Widgets (Row 0)
        ttk.Label(self.control_frame, text="Input File:").grid(row=0, column=0, sticky=tk.W)
        self.input_entry = ttk.Entry(self.control_frame, textvariable=self.input_path_var, width=40)
        self.input_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 10))
        self.browse_button = ttk.Button(self.control_frame, text="Browse", command=self.select_file)
        self.browse_button.grid(row=0, column=2, sticky=tk.W, padx=(5, 0))

        # Output File Widgets (Row 1)
        ttk.Label(self.control_frame, text="Output File:").grid(row=1, column=0, sticky=tk.W)
        self.output_entry = ttk.Entry(self.control_frame, textvariable=self.output_path_var, width=40)
        self.output_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 10))

        # Gamma Adjustment Widgets (Row 2)
        ttk.Label(self.control_frame, text="Gamma:").grid(row=2, column=0, sticky=tk.W)
        self.gamma_slider = ttk.Scale(
            self.control_frame, variable=self.gamma_var, from_=0.1, to=3.0,
            orient=tk.HORIZONTAL, length=200, command=self.update_frame_preview
        )
        self.gamma_slider.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 10))
        self.gamma_entry = ttk.Entry(self.control_frame, textvariable=self.gamma_var, width=5)
        self.gamma_entry.grid(row=2, column=2, sticky=tk.W, padx=(5, 0))
        self.gamma_entry.bind('<Return>', self.update_frame_preview)

        # GPU & Filter (Row 3)
        self.gpu_accel_checkbutton = ttk.Checkbutton(
            self.control_frame, text="Enable GPU Acceleration",
            variable=self.gpu_accel_var, command=self.check_gpu_acceleration
        )
        self.gpu_accel_checkbutton.grid(row=3, column=0, sticky=tk.W, pady=(5, 0))

        filter_frame = ttk.Frame(self.control_frame)
        filter_frame.grid(row=3, column=1, sticky=tk.W, padx=(5, 10), pady=(5, 0))
        
        self.filter_combobox = ttk.Combobox(
            filter_frame, textvariable=self.filter_var, values=self.filter_options,
            state='readonly', width=15
        )
        self.filter_combobox.grid(row=0, column=0, padx=(0, 5))
        self.filter_combobox.bind('<<ComboboxSelected>>', self.update_frame_preview)

        info_button = ttk.Label(filter_frame, text="ⓘ", cursor="hand2")
        info_button.grid(row=0, column=1)
        tooltip_text = ("Static: Basic HDR to SDR conversion with fixed parameters\n"
                       "Dynamic: Adaptive conversion that analyzes video brightness")
        info_button.bind('<Enter>', lambda e: self.show_tooltip(e, tooltip_text))
        info_button.bind('<Leave>', self.hide_tooltip)

        # Display Image & Tonemapper (Row 4)
        display_frame = ttk.Frame(self.control_frame)
        display_frame.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))

        self.display_image_checkbutton = ttk.Checkbutton(
            display_frame, text="Display Frame Preview",
            variable=self.display_image_var, command=self.update_frame_preview
        )
        self.display_image_checkbutton.grid(row=0, column=0, sticky=tk.W)

        self.tonemap_combobox = ttk.Combobox(
            display_frame, textvariable=self.tonemap_var, values=TONEMAP,
            state='readonly', width=15
        )
        self.tonemap_combobox.grid(row=0, column=1, padx=(18, 0), sticky=tk.W)
        self.tonemap_combobox.bind('<<ComboboxSelected>>', self.update_frame_preview)

        info_button_tonemap = ttk.Label(display_frame, text="ⓘ", cursor="hand2")
        info_button_tonemap.grid(row=0, column=2, padx=(5, 0))
        tooltip_text_tonemap = (
            "Reinhard: Basic HDR to SDR conversion\n"
            "Mobius: Natural-looking conversion\n"
            "Hable: Game-like conversion (Cyberpunk 2077)"
        )
        info_button_tonemap.bind('<Enter>', lambda e: self.show_tooltip(e, tooltip_text_tonemap))
        info_button_tonemap.bind('<Leave>', self.hide_tooltip)

        # [수정됨] Action Frame (Convert 버튼이 화면 밖으로 밀려나지 않게 상단에 고정) (Row 5)
        self.action_frame = ttk.Frame(self.control_frame)
        self.action_frame.grid(row=5, column=0, columnspan=3, pady=(15, 5), sticky=tk.W)
        self.action_frame.grid_remove()

        self.open_after_conversion_checkbutton = ttk.Checkbutton(
            self.action_frame, text="Open output file after conversion",
            variable=self.open_after_conversion_var
        )
        self.open_after_conversion_checkbutton.grid(row=0, column=0, padx=(5, 10), sticky=tk.W)

        self.convert_button = ttk.Button(self.action_frame, text="Convert", command=self.convert_video)
        self.convert_button.grid(row=0, column=1, padx=(5, 5))

        self.cancel_button = ttk.Button(self.action_frame, text="Cancel", command=self.cancel_conversion)
        self.cancel_button.grid(row=0, column=2, padx=(5, 5))
        self.cancel_button.grid_remove()

        # [수정됨] Progress Bar (레이아웃 상단 고정) (Row 6)
        self.progress_bar = ttk.Progressbar(self.control_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 5))

        # [수정됨] Error Label (다른 버튼에 가려지지 않게 최하단으로 분리) (Row 7)
        self.error_label = ttk.Label(self.control_frame, text='', foreground='red')
        self.error_label.grid(row=7, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))

        # Image Frame (Root Row 1)
        self.image_frame = ttk.Frame(self.root, padding="10")
        self.image_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.image_frame.grid_remove()

        self.original_title_label = ttk.Label(self.image_frame, text="Original (HDR):")
        self.converted_title_label = ttk.Label(self.image_frame, text="Converted (SDR):")
        
        self.original_image_label = ttk.Label(self.image_frame)
        self.original_image_label.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 10))
        self.converted_image_label = ttk.Label(self.image_frame)
        self.converted_image_label.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 0))

        self.button_container = ttk.Frame(self.image_frame)
        self.button_container.grid(row=1, column=2, sticky=(tk.N), padx=(5, 10))
        self.button_container.grid_remove()
        
        self.frame_buttons = []
        style = ttk.Style()
        style.configure('Selected.TButton', relief='sunken')

        for i in range(1, 6):
            btn = ttk.Button(self.button_container, text=str(i), command=lambda idx=i: self.on_frame_button_click(idx))
            btn.grid(row=i-1, column=0, pady=5)
            self.frame_buttons.append(btn)

        self.interactable_elements = [
            self.browse_button, self.convert_button, self.gamma_slider,
            self.open_after_conversion_checkbutton, self.display_image_checkbutton,
            self.input_entry, self.output_entry, self.gamma_entry, self.gpu_accel_checkbutton
        ]

    def configure_grid(self):
        self.control_frame.columnconfigure(0, weight=0)
        self.control_frame.columnconfigure(1, weight=1)
        self.control_frame.columnconfigure(2, weight=0)
        
        self.image_frame.columnconfigure(0, weight=1)
        self.image_frame.columnconfigure(1, weight=1)
        self.image_frame.columnconfigure(2, weight=0)
        
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

    def select_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("All Video Files", "*.mp4 *.mkv *.mov *.avi *.webm *.m4v"),
                ("MP4 files", "*.mp4"),
                ("MKV files", "*.mkv"),
                ("MOV files", "*.mov"),
