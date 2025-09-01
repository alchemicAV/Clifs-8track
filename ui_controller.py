"""
UI Controller - Main GUI interface optimized for elderly users
UPDATED VERSION with volume faders and FX controls - FIXED layout issues
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import threading
import time
import math
import numpy as np

class MultitrackUI:
	def __init__(self, root, audio_engine, track_manager, project_manager):
		self.root = root
		self.audio_engine = audio_engine
		self.track_manager = track_manager
		self.project_manager = project_manager
		
		# UI state
		self.is_recording = False
		self.is_playing = False
		self.current_time = 0
		
		# Performance optimization caches
		self._level_cache = {}
		self._cursor_cache = {}
		self._waveform_cache = set()
		self._segment_cache = {}
		self._last_update_state = {}
		
		# Color scheme - updated with teal theme
		self.colors = {
			'bg': '#008080',  # Main teal background
			'fg': '#ffffff',  # White text
			'upper_bg': '#2F4F4F',  # Dark teal for upper windows
			'button_normal': '#2F4F4F',  # Dark teal for buttons
			'button_active': '#4682B4',  # Steel blue for active buttons
			'button_armed': '#cc4444',  # Keep red for armed
			'button_recording': '#ff0000',  # Keep red for recording
			'button_playing': '#44cc44',  # Keep green for playing
			'button_muted': '#888888',  # Keep gray for muted
			'button_disabled': '#666666',  # Keep gray for disabled
			'text': '#ffffff',
			'fx_button': '#8A2BE2',  # Purple for FX buttons
			'fx_active': '#9932CC'   # Darker purple for active FX
		}
		
		# Track UI elements storage
		self.track_widgets = {}
		self.volume_faders = {}  # Store volume fader references
		self.fx_buttons = {}     # Store FX button references
		self.track_name_labels = {}  # Store track name labels for faders
		
		# Get project name before creating UI
		self.get_project_name_at_startup()
		
		self.create_ui()
		self.start_optimized_ui_update_thread()

		self.audio_engine.set_master_volume(1.0)  # 75% = 0 dB
		
	def get_project_name_at_startup(self):
		"""Prompt for project name at startup"""
		# Hide the main window temporarily
		self.root.withdraw()
		
		project_name = simpledialog.askstring(
			"Project Name",
			"Enter a name for your recording project:",
			initialvalue="My Recording Session"
		)
		
		if not project_name or project_name.strip() == "":
			project_name = "Default Project"
			
		# Set project name and create directories
		self.project_manager.set_project_name(project_name)
		
		# Show the main window
		self.root.deiconify()
		
		return project_name
		
	def create_project_controls(self):
		"""Create project name display and project management buttons"""
		project_frame = tk.Frame(self.root, bg=self.colors['upper_bg'])
		project_frame.pack(pady=(10, 5), padx=20, fill='x')
		
		tk.Label(
			project_frame,
			text="Current Project:",
			font=('Arial', 14, 'bold'),
			bg=self.colors['upper_bg'],
			fg=self.colors['fg']
		).pack(side='left', padx=(0, 10))
		
		# Display project name as read-only text
		self.project_name_display = tk.Label(
			project_frame,
			text=self.project_manager.current_project_name,
			font=('Arial', 14, 'bold'),
			bg='#404040',
			fg='#ffffff',
			relief='sunken',
			bd=1,
			width=30,
			anchor='w'
		)
		self.project_name_display.pack(side='left', padx=5)
		
		# New project button
		new_project_button = tk.Button(
			project_frame,
			text="NEW PROJECT",
			command=self.new_project,
			font=('Arial', 12, 'bold'),
			bg=self.colors['button_normal'],
			fg=self.colors['fg'],
			activebackground=self.colors['button_active'],
			relief='raised',
			bd=2
		)
		new_project_button.pack(side='left', padx=(10, 5))
		
		# Save project button
		save_button = tk.Button(
			project_frame,
			text="SAVE PROJECT",
			command=self.save_project,
			font=('Arial', 12, 'bold'),
			bg=self.colors['button_normal'],
			fg=self.colors['fg'],
			activebackground=self.colors['button_active'],
			relief='raised',
			bd=2
		)
		save_button.pack(side='left', padx=5)
		
		# Load project button
		load_button = tk.Button(
			project_frame,
			text="LOAD PROJECT",
			command=self.load_project,
			font=('Arial', 12, 'bold'),
			bg=self.colors['button_normal'],
			fg=self.colors['fg'],
			activebackground=self.colors['button_active'],
			relief='raised',
			bd=2
		)
		load_button.pack(side='left', padx=5)
		
		# Export mixdown button
		export_button = tk.Button(
			project_frame,
			text="EXPORT MP3",
			command=self.export_mixdown,
			font=('Arial', 12, 'bold'),
			bg='#4169E1',  # Royal blue for export
			fg=self.colors['fg'],
			activebackground='#6495ED',
			relief='raised',
			bd=2
		)
		export_button.pack(side='left', padx=5)
		
	def create_device_controls(self):
		"""Create device selector dropdowns"""
		device_frame = tk.Frame(self.root, bg=self.colors['upper_bg'])
		device_frame.pack(pady=5, padx=(20, 850), fill='x')
		
		# Input device selector
		input_frame = tk.Frame(device_frame, bg=self.colors['upper_bg'])
		input_frame.pack(side='left', padx=(0, 20))
		
		tk.Label(
			input_frame,
			text="Input Device:",
			font=('Arial', 10, 'bold'),
			bg=self.colors['upper_bg'],
			fg=self.colors['fg']
		).pack(anchor='w')
		
		self.input_device_var = tk.StringVar()
		self.input_device_combo = ttk.Combobox(
			input_frame,
			textvariable=self.input_device_var,
			state='readonly',
			width=40,
			font=('Arial', 9)
		)
		self.input_device_combo.pack()
		self.input_device_combo.bind('<<ComboboxSelected>>', self.on_input_device_change)
		
		# Output device selector
		output_frame = tk.Frame(device_frame, bg=self.colors['upper_bg'])
		output_frame.pack(side='left')
		
		tk.Label(
			output_frame,
			text="Output Device:",
			font=('Arial', 10, 'bold'),
			bg=self.colors['upper_bg'],
			fg=self.colors['fg']
		).pack(anchor='w')
		
		self.output_device_var = tk.StringVar()
		self.output_device_combo = ttk.Combobox(
			output_frame,
			textvariable=self.output_device_var,
			state='readonly',
			width=40,
			font=('Arial', 9)
		)
		self.output_device_combo.pack()
		self.output_device_combo.bind('<<ComboboxSelected>>', self.on_output_device_change)
		
		# Populate device lists
		self.populate_device_lists()
		
		# Add latency info display
		self.create_latency_info()
		
	def create_latency_info(self):
		"""Create latency information display with recalibrate button"""
		latency_frame = tk.Frame(self.root, bg=self.colors['upper_bg'])
		latency_frame.pack(pady=2, padx=(20, 800), fill='x')
		
		# Recalibrate button
		recalibrate_button = tk.Button(
			latency_frame,
			text="RECALIBRATE",
			command=self.recalibrate_latency,
			font=('Arial', 9, 'bold'),
			bg=self.colors['button_normal'],
			fg=self.colors['fg'],
			activebackground=self.colors['button_active'],
			relief='raised',
			bd=1,
			width=12,
			height=1
		)
		recalibrate_button.pack(side='left', padx=(15, 0))

		self.latency_label = tk.Label(
			latency_frame,
			text="Measuring latency...",
			font=('Arial', 9),
			bg=self.colors['upper_bg'],
			fg='#cccccc'
		)
		self.latency_label.pack(side='left')
		
		# Update latency info periodically
		self.update_latency_info()
		
	def update_latency_info(self):
		"""Update latency information display"""
		try:
			latency_info = self.audio_engine.get_latency_info()
			if latency_info['calibrated']:
				status = f"✓ Latency: {latency_info['measured_ms']:.1f}ms (compensated)"
				color = '#90EE90'  # Light green
			else:
				status = f"⚠ Estimating latency: {latency_info['measured_ms']:.1f}ms"
				color = '#FFD700'  # Gold
			
			self.latency_label.config(text=status, fg=color)
		except:
			pass
		
		# Update every 5 seconds
		self.root.after(5000, self.update_latency_info)
		
	def create_ui(self):
		"""Create the main UI layout"""
		self.create_project_controls()
		self.create_device_controls()
		self.create_top_controls()
		self.create_track_area()
		self.create_metronome_controls()
		self.create_volume_faders()  # New volume faders section
		self.setup_focus_handling()
		
	def create_top_controls(self):
		"""Create main transport controls"""
		top_frame = tk.Frame(self.root, bg=self.colors['upper_bg'])
		top_frame.pack(pady=20, padx=(20, 700), fill='x')
		
		# Main transport buttons
		button_style = {
			'font': ('Arial', 16, 'bold'),
			'width': 8,
			'height': 2,
			'bg': self.colors['button_normal'],
			'fg': self.colors['fg'],
			'activebackground': self.colors['button_active'],
			'relief': 'raised',
			'bd': 3
		}
		
		self.play_button = tk.Button(
			top_frame, 
			text="PLAY", 
			command=self.start_playback,
			**button_style
		)
		self.play_button.pack(side='left', padx=10)
		
		self.stop_button = tk.Button(
			top_frame, 
			text="STOP", 
			command=self.stop_all,
			**button_style
		)
		self.stop_button.pack(side='left', padx=10)
		
		# Instructions label
		instruction_label = tk.Label(
			top_frame,
			text="ARM a track, then press PLAY to record.",
			font=('Arial', 12),
			bg=self.colors['upper_bg'],
			fg=self.colors['fg']
		)
		instruction_label.pack(side='left', padx=20)
		
		# Time display
		self.time_label = tk.Label(
			top_frame,
			text="00:00.000",
			font=('Arial', 20, 'bold'),
			bg=self.colors['upper_bg'],
			fg=self.colors['fg']
		)
		self.time_label.pack(side='left', padx=20)
		
	def create_track_area(self):
		"""Create the 8-track area"""
		# Create scrollable frame for tracks with left padding
		track_canvas = tk.Canvas(
			self.root, 
			height=420, 
			highlightthickness=0, 
			bg=self.colors['bg']
		)
		track_frame = tk.Frame(track_canvas, bg=self.colors['bg'])
		
		track_canvas.pack(fill='x', anchor='w', expand=False, padx=(20, 620), pady=10)
		track_canvas.create_window((0, 0), window=track_frame, anchor='nw')
		
		# Track headers with dark teal background
		header_frame = tk.Frame(track_frame, bg='#2F4F4F')
		header_frame.pack(fill='x', pady=(0, 10))
		
		# Headers
		headers = ['Track', 'Level', ' ', 'Status', 'Waveform']
		header_widths = [7, 6, 20, 15, 28]
		
		for i, (header, width) in enumerate(zip(headers, header_widths)):
			tk.Label(
				header_frame,
				text=header,
				font=('Arial', 12, 'bold'),
				bg='#2F4F4F',
				fg=self.colors['fg'],
				width=width
			).pack(side='left', padx=5)
		
		# Create 8 track strips
		for track_num in range(1, 9):
			self.create_track_strip(track_frame, track_num)
			
	def create_track_strip(self, parent, track_num):
		"""Create a single track strip with controls"""
		track_frame = tk.Frame(parent, relief='ridge', bd=2, bg='#2F4F4F')
		track_frame.pack(fill='x', pady=2)
		
		button_style = {
			'font': ('Arial', 12, 'bold'),
			'width': 6,
			'height': 1,
			'relief': 'raised',
			'bd': 2
		}
		
		# Track name entry (editable text box)
		track_name_var = tk.StringVar(value=f"Track {track_num}")
		track_name_entry = tk.Entry(
			track_frame,
			textvariable=track_name_var,
			font=('Arial', 11, 'bold'),
			bg='#404040',
			fg=self.colors['fg'],
			insertbackground=self.colors['fg'],
			width=8,
			justify='center',
			bd=1,
			relief='sunken'
		)
		track_name_entry.pack(side='left', padx=5)
		track_name_entry.bind('<Return>', lambda e: self.on_track_name_change(track_num, track_name_var.get()))
		track_name_entry.bind('<FocusOut>', lambda e: self.on_track_name_change(track_num, track_name_var.get()))
		
		# Level meter frame
		level_frame = tk.Frame(track_frame, width=60, height=30, bg='#2F4F4F')
		level_frame.pack(side='left', padx=5)
		level_frame.pack_propagate(False)
		
		# LED level indicator
		level_canvas = tk.Canvas(
			level_frame,
			width=50,
			height=20,
			bg='#1a1a1a',
			highlightthickness=0
		)
		level_canvas.pack(padx=5, pady=2)
		
		# Peak indicator
		peak_indicator = tk.Label(
			level_frame,
			text="PEAK",
			font=('Arial', 6, 'bold'),
			bg='#2F4F4F',
			fg='#333333',
			width=8
		)
		peak_indicator.pack(pady=(2, 0))
		
		# ARM button
		arm_button = tk.Button(
			track_frame,
			text="ARM",
			command=lambda: self.toggle_arm(track_num),
			bg=self.colors['button_normal'],
			fg=self.colors['fg'],
			activebackground=self.colors['button_active'],
			**button_style
		)
		arm_button.pack(side='left', padx=5)
		
		# MUTE button
		mute_button = tk.Button(
			track_frame,
			text="MUTE",
			command=lambda: self.toggle_mute(track_num),
			bg=self.colors['button_normal'],
			fg=self.colors['fg'],
			activebackground=self.colors['button_active'],
			**button_style
		)
		mute_button.pack(side='left', padx=5)
		
		# CLEAR button
		clear_button = tk.Button(
			track_frame,
			text="CLEAR",
			command=lambda: self.clear_track(track_num),
			bg=self.colors['button_normal'],
			fg=self.colors['fg'],
			activebackground=self.colors['button_active'],
			**button_style
		)
		clear_button.pack(side='left', padx=5)
		
		# Status label
		status_label = tk.Label(
			track_frame,
			text="Empty",
			font=('Arial', 10),
			bg='#2F4F4F',
			fg=self.colors['fg'],
			width=13,
			anchor='w'
		)
		status_label.pack(side='left', padx=10)
		
		# Waveform display
		waveform_frame = tk.Frame(track_frame, width=320, height=40, bg='#2F4F4F')
		waveform_frame.pack(side='left', padx=5)
		waveform_frame.pack_propagate(False)
		
		waveform_canvas = tk.Canvas(
			waveform_frame,
			width=300,
			height=35,
			bg='#1a1a1a',
			highlightthickness=1,
			highlightbackground='#444444'
		)
		waveform_canvas.pack(padx=10, pady=2)
		
		# Store references to track widgets
		self.track_widgets[track_num] = {
			'frame': track_frame,
			'track_name_entry': track_name_entry,
			'track_name_var': track_name_var,
			'arm_button': arm_button,
			'mute_button': mute_button,
			'clear_button': clear_button,
			'status_label': status_label,
			'level_canvas': level_canvas,
			'peak_indicator': peak_indicator,
			'waveform_canvas': waveform_canvas
		}
		
	def create_metronome_controls(self):
		"""Create metronome controls with editable BPM text box"""
		metronome_frame = tk.Frame(self.root, bg=self.colors['bg'])
		metronome_frame.pack(anchor='w', pady=10, padx=(20, 470), fill='x')
		
		# Metronome label
		tk.Label(
			metronome_frame,
			text="METRONOME",
			font=('Arial', 14, 'bold'),
			bg=self.colors['bg'],
			fg=self.colors['fg']
		).pack(side='left', padx=10)
		
		# Metronome on/off button
		self.metronome_button = tk.Button(
			metronome_frame,
			text="OFF",
			command=self.toggle_metronome,
			font=('Arial', 12, 'bold'),
			width=6,
			height=1,
			bg=self.colors['button_normal'],
			fg=self.colors['fg'],
			activebackground=self.colors['button_active'],
			relief='raised',
			bd=2
		)
		self.metronome_button.pack(side='left', padx=10)
		
		# Volume control
		tk.Label(
			metronome_frame,
			text="VOL:",
			font=('Arial', 12, 'bold'),
			bg=self.colors['bg'],
			fg=self.colors['fg']
		).pack(side='left', padx=(20, 5))
		
		self.metronome_volume = tk.Scale(
			metronome_frame,
			from_=0,
			to=100,
			orient='horizontal',
			length=100,
			bg=self.colors['bg'],
			fg=self.colors['fg'],
			highlightthickness=0,
			troughcolor='#404040',
			activebackground=self.colors['button_active'],
			command=self.on_metronome_volume_change
		)
		self.metronome_volume.set(50)  # Default to 50%
		self.metronome_volume.pack(side='left', padx=5)
		
		# BPM controls with editable text box
		tk.Label(
			metronome_frame,
			text="BPM:",
			font=('Arial', 12, 'bold'),
			bg=self.colors['bg'],
			fg=self.colors['fg']
		).pack(side='left', padx=(20, 5))
		
		# BPM editable text box
		self.bpm_var = tk.StringVar(value="120")
		self.bpm_entry = tk.Entry(
			metronome_frame,
			textvariable=self.bpm_var,
			font=('Arial', 12, 'bold'),
			bg='#404040',
			fg=self.colors['fg'],
			insertbackground=self.colors['fg'],
			width=4,
			justify='center',
			bd=1,
			relief='sunken'
		)
		self.bpm_entry.pack(side='left', padx=5)
		self.bpm_entry.bind('<Return>', self.on_bpm_entry_change)
		self.bpm_entry.bind('<FocusOut>', self.on_bpm_entry_change)
		
		# BPM adjustment buttons (single click only)
		bpm_button_style = {
			'font': ('Arial', 12, 'bold'),
			'width': 3,
			'height': 1,
			'bg': self.colors['button_normal'],
			'fg': self.colors['fg'],
			'activebackground': self.colors['button_active'],
			'relief': 'raised',
			'bd': 2
		}
		
		tk.Button(
			metronome_frame,
			text="-",
			command=lambda: self.adjust_bpm(-1),
			**bpm_button_style
		).pack(side='left', padx=2)
		
		tk.Button(
			metronome_frame,
			text="+",
			command=lambda: self.adjust_bpm(1),
			**bpm_button_style
		).pack(side='left', padx=2)

		# Master volume control
		tk.Label(
			metronome_frame,
			text="MASTER VOLUME:",
			font=('Arial', 12, 'bold'),
			bg=self.colors['bg'],
			fg=self.colors['fg']
		).pack(side='left', padx=(30, 5))

		self.master_volume = tk.Scale(
			metronome_frame,
			from_=0,
			to=100,
			orient='horizontal',
			length=120,
			bg=self.colors['bg'],
			fg=self.colors['fg'],
			highlightthickness=0,
			troughcolor='#404040',
			activebackground=self.colors['button_active'],
			command=self.on_master_volume_change
		)
		self.master_volume.set(75)  # Default to 75% (0 dB)
		self.master_volume.pack(side='left', padx=5)
		
	def create_volume_faders(self):
		"""Create volume faders section at bottom in 2x4 grid layout"""
		# Main volume faders frame with fixed height
		faders_main_frame = tk.Frame(self.root, bg=self.colors['bg'], height=180)
		faders_main_frame.pack(fill='x', pady=(10, 5), padx=20)
		# faders_main_frame.pack_propagate(False)  # Prevent frame from shrinking
		
		# Title label
		title_label = tk.Label(
			faders_main_frame,
			text="TRACK VOLUMES & EFFECTS",
			font=('Arial', 14, 'bold'),
			bg=self.colors['bg'],
			fg=self.colors['fg']
		)
		title_label.pack(pady=(5, 10))
		
		# Create 2x4 grid container
		grid_frame = tk.Frame(faders_main_frame, bg=self.colors['bg'])
		grid_frame.pack(expand=True, fill='both', padx=10)
		
		# Create two rows
		top_row_frame = tk.Frame(grid_frame, bg=self.colors['bg'])
		top_row_frame.pack(fill='x', pady=(0, 5))
		
		bottom_row_frame = tk.Frame(grid_frame, bg=self.colors['bg'])
		bottom_row_frame.pack(fill='x')
		
		# Top row: Tracks 1, 3, 5, 7
		for i, track_num in enumerate([1, 3, 5, 7]):
			self.create_volume_fader_grid_cell(top_row_frame, track_num)
		
		# Bottom row: Tracks 2, 4, 6, 8
		for i, track_num in enumerate([2, 4, 6, 8]):
			self.create_volume_fader_grid_cell(bottom_row_frame, track_num)

	def create_volume_fader_grid_cell(self, parent_row, track_num):
		"""Create a single grid cell for volume fader"""
		# Cell frame - each takes 1/4 of the width
		cell_frame = tk.Frame(parent_row, bg=self.colors['upper_bg'], relief='ridge', bd=1)
		cell_frame.pack(side='left', fill='both', expand=True, padx=2, pady=1)
		
		# Track name at top
		track = self.track_manager.get_track(track_num)
		track_name = track.name if track else f"Track {track_num}"
		
		track_name_label = tk.Label(
			cell_frame,
			text=track_name,
			font=('Arial', 10, 'bold'),
			bg=self.colors['upper_bg'],
			fg=self.colors['fg'],
			anchor='w'
		)
		track_name_label.pack(side='left', pady=(3, 5))
		
		# FX button in middle
		fx_button = tk.Button(
			cell_frame,
			text="FX",
			command=lambda: self.show_fx_menu(track_num),
			font=('Arial', 9, 'bold'),
			width=6,
			height=1,
			bg=self.colors['fx_button'],
			fg=self.colors['fg'],
			activebackground=self.colors['fx_active'],
			relief='raised',
			bd=2
		)
		fx_button.pack(side='left', pady=(5, 5))
		
		# Volume controls at bottom
		volume_frame = tk.Frame(cell_frame, bg=self.colors['upper_bg'])
		volume_frame.pack(fill='x', pady=(0, 3), padx=3)
		
		# VOL label
		tk.Label(
			volume_frame,
			text="VOL:",
			font=('Arial', 8, 'bold'),
			bg=self.colors['upper_bg'],
			fg=self.colors['fg']
		).pack(side='left')
		
		# Volume fader (horizontal, more compact)
		volume_fader = tk.Scale(
			volume_frame,
			from_=0,
			to=100,
			orient='horizontal',
			length=180,  # Fit within grid cell
			width=12,
			bg=self.colors['upper_bg'],
			fg=self.colors['fg'],
			highlightthickness=0,
			troughcolor='#404040',
			activebackground=self.colors['button_active'],
			command=lambda val, tn=track_num: self.on_volume_change(tn, val),
			showvalue=True,
			font=('Arial', 8)
		)
		volume_fader.set(75)  # Default to 75%
		volume_fader.pack(pady=(0, 3))
		
		# Store references
		self.volume_faders[track_num] = volume_fader
		self.fx_buttons[track_num] = fx_button  
		self.track_name_labels[track_num] = track_name_label
		
		# Initialize audio engine with default volume
		self.audio_engine.set_track_volume(track_num, 0.75)
	
	def show_fx_menu(self, track_num):
		"""Show FX effects menu for a track"""
		fx_menu = tk.Menu(self.root, tearoff=0, bg=self.colors['upper_bg'], fg=self.colors['fg'])
		
		# Current FX status
		current_fx = self.audio_engine.get_track_fx(track_num)
		
		# None option
		fx_menu.add_command(
			label="None" + (" ✓" if current_fx == "none" else ""),
			command=lambda: self.set_track_fx(track_num, "none")
		)
		
		fx_menu.add_separator()
		
		# Wide Hall preset
		fx_menu.add_command(
			label="Wide Hall" + (" ✓" if current_fx == "wide_hall" else ""),
			command=lambda: self.set_track_fx(track_num, "wide_hall")
		)
		
		# Studio preset  
		fx_menu.add_command(
			label="Studio" + (" ✓" if current_fx == "studio" else ""),
			command=lambda: self.set_track_fx(track_num, "studio")
		)
		
		# Compressor only preset
		fx_menu.add_command(
			label="Compressor" + (" ✓" if current_fx == "compressor" else ""),
			command=lambda: self.set_track_fx(track_num, "compressor")
		)
		
		# Get button position for menu placement
		fx_button = self.fx_buttons[track_num]
		x = fx_button.winfo_rootx()
		y = fx_button.winfo_rooty() + fx_button.winfo_height()
		
		fx_menu.post(x, y)
	
	def set_track_fx(self, track_num, fx_type):
		"""Set FX for a track"""
		self.audio_engine.set_track_fx(track_num, fx_type)
		
		# Update FX button appearance
		fx_button = self.fx_buttons[track_num]
		if fx_type == "none":
			fx_button.config(bg=self.colors['fx_button'])
		else:
			fx_button.config(bg=self.colors['fx_active'])
			
		print(f"Set track {track_num} FX to: {fx_type}")
	
	def on_volume_change(self, track_num, value):
		"""Handle volume fader change"""
		volume = float(value) / 100.0  # Convert to 0.0-1.0 range
		self.audio_engine.set_track_volume(track_num, volume)
		self.track_manager.set_track_volume(track_num, volume)
		
	def recalibrate_latency(self):
		"""Manually recalibrate audio latency with blocking popup"""
		# Create modal popup
		self.calibration_popup = tk.Toplevel(self.root)
		self.calibration_popup.title("Calibrating")
		self.calibration_popup.geometry("300x120")
		self.calibration_popup.configure(bg=self.colors['upper_bg'])
		self.calibration_popup.transient(self.root)
		self.calibration_popup.grab_set()  # Make it modal
		self.calibration_popup.resizable(False, False)
	
		# Center the popup
		self.calibration_popup.update_idletasks()
		x = (self.calibration_popup.winfo_screenwidth() // 2) - (300 // 2)
		y = (self.calibration_popup.winfo_screenheight() // 2) - (120 // 2)
		self.calibration_popup.geometry(f"300x120+{x}+{y}")
	
		# Popup content
		tk.Label(
			self.calibration_popup,
			text="Recalibrating...",
			font=('Arial', 14, 'bold'),
			bg=self.colors['upper_bg'],
			fg=self.colors['fg']
		).pack(pady=20)
	
		tk.Label(
			self.calibration_popup,
			text="Please wait while audio latency is measured.",
			font=('Arial', 10),
			bg=self.colors['upper_bg'],
			fg=self.colors['fg']
		).pack(pady=10)
	
		# Update display
		self.calibration_popup.update()
	
		def calibration_thread():
			try:
				# Run latency measurement
				self.audio_engine.measure_latency()
			
				# Close popup and update display in main thread
				self.root.after(0, self.calibration_complete)
			except Exception as e:
				self.root.after(0, lambda: self.calibration_error(str(e)))
	
		# Run calibration in background thread
		threading.Thread(target=calibration_thread, daemon=True).start()
		
	def calibration_complete(self):
		"""Handle calibration completion"""
		if hasattr(self, 'calibration_popup'):
			self.calibration_popup.destroy()
			delattr(self, 'calibration_popup')
		
		# Update latency display
		self.update_latency_info()
		
	def calibration_error(self, error_msg):
		"""Handle calibration error"""
		if hasattr(self, 'calibration_popup'):
			self.calibration_popup.destroy()
			delattr(self, 'calibration_popup')
	
		self.latency_label.config(text=f"Calibration failed: {error_msg}", fg='#FF6B6B')

	def export_mixdown(self):
		"""Export project as MP3 mixdown"""
		if not self.track_manager.has_any_data():
			messagebox.showinfo("No Data", "No recorded tracks to export.")
			return
		
		project_name = self.project_name_display.cget('text')
		if not project_name or project_name.strip() == "":
			project_name = "Untitled"
		
		try:
			# Show progress dialog
			progress_window = tk.Toplevel(self.root)
			progress_window.title("Exporting...")
			progress_window.geometry("300x100")
			progress_window.configure(bg=self.colors['upper_bg'])
			progress_window.transient(self.root)
			progress_window.grab_set()
			
			progress_label = tk.Label(
				progress_window,
				text="Creating MP3 mixdown...",
				font=('Arial', 12),
				bg=self.colors['upper_bg'],
				fg=self.colors['fg']
			)
			progress_label.pack(pady=30)
			
			progress_window.update()
			
			# Export in a separate thread to avoid UI blocking
			def export_thread():
				try:
					success = self.audio_engine.export_mixdown_mp3(project_name)
					
					# Update UI in main thread
					self.root.after(0, lambda: self.export_complete(progress_window, success, project_name))
					
				except Exception as e:
					self.root.after(0, lambda: self.export_error(progress_window, str(e)))
			
			threading.Thread(target=export_thread, daemon=True).start()
			
		except Exception as e:
			messagebox.showerror("Export Error", f"Failed to start export: {e}")
	
	def export_complete(self, progress_window, success, project_name):
		"""Handle export completion"""
		progress_window.destroy()
		
		if success:
			messagebox.showinfo(
				"Export Complete", 
				f"Mixdown exported successfully!\n\nFile: {project_name}_mixdown.mp3\nLocation: exported_mp3s folder"
			)
		else:
			messagebox.showerror("Export Error", "Failed to export mixdown.")
	
	def export_error(self, progress_window, error_msg):
		"""Handle export error"""
		progress_window.destroy()
		messagebox.showerror("Export Error", f"Export failed: {error_msg}")
	
	def update_track_name_labels(self):
		"""Update track name labels on volume faders"""
		for track_num in range(1, 9):
			track = self.track_manager.get_track(track_num)
			if track and track_num in self.track_name_labels:
				self.track_name_labels[track_num].config(text=track.name)

	# Button action methods
	def new_project(self):
		"""Create a new project - prompt to save current project first"""
		# Check if current project has any data
		if self.track_manager.has_any_data():
			result = messagebox.askyesnocancel(
				"New Project",
				"Do you want to save the current project before creating a new one?"
			)
			if result is None:  # Cancel
				return
			elif result:  # Yes - save first
				self.save_project()
	
		# Prompt for new project name
		new_project_name = simpledialog.askstring(
			"New Project",
			"Enter a name for your new project:",
			initialvalue="My Recording Session"
		)
	
		if not new_project_name or new_project_name.strip() == "":
			new_project_name = "New Project"
	
		# Clear all current data
		self.audio_engine.clear_all_project_data()
		self.track_manager.reset_all_tracks()
	
		# Reset audio engine parameters to defaults
		self.audio_engine.set_bpm(120)
		self.audio_engine.set_metronome(False)
	
		# Reset all track volumes to default (75%)
		for track_num in range(1, 9):
			self.audio_engine.set_track_volume(track_num, 0.75)
			self.track_manager.set_track_volume(track_num, 0.75)
	
		# Reset all FX to none
		for track_num in range(1, 9):
			self.audio_engine.set_track_fx(track_num, "none")
	
		# Create new project
		self.project_manager.create_new_project(new_project_name)
		recordings_folder = self.project_manager.set_project_name(new_project_name)
		self.audio_engine.set_recordings_directory(recordings_folder)
	
		# Update UI elements to defaults
		self.project_name_display.config(text=new_project_name)
	
		# Reset BPM display
		self.bpm_var.set("120")
	
		# Reset metronome button
		self.metronome_button.config(text="OFF", bg=self.colors['button_normal'])
	
		# Reset metronome volume
		self.metronome_volume.set(50)
		self.audio_engine.set_metronome_volume(0.5)
	
		# Reset track names to defaults and update UI
		for track_num in range(1, 9):
			track = self.track_manager.get_track(track_num)
			if track:
				track.name = f"Track {track_num}"
			
			widgets = self.track_widgets.get(track_num)
			if widgets:
				widgets['track_name_var'].set(f"Track {track_num}")
	
		# Reset volume faders to default (75%)
		for track_num in range(1, 9):
			if track_num in self.volume_faders:
				self.volume_faders[track_num].set(75)
	
		# Update volume fader labels
		self.update_track_name_labels()
	
		# Reset all FX buttons to normal state
		for track_num in range(1, 9):
			if track_num in self.fx_buttons:
				self.fx_buttons[track_num].config(bg=self.colors['fx_button'])
	
		# Clear UI caches to force refresh
		self.clear_ui_caches()
	
		print(f"✓ Created new project: {new_project_name}")
		print("✓ All parameters reset to defaults")
		
	def on_track_name_change(self, track_num, new_name):
		"""Handle track name change from Entry widget"""
		if new_name.strip():
			track = self.track_manager.get_track(track_num)
			if track:
				track.name = new_name.strip()
				# Update the volume fader label
				if track_num in self.track_name_labels:
					self.track_name_labels[track_num].config(text=track.name)
				# Force UI state update
				state_key = f'track_{track_num}_state'
				if state_key in self._last_update_state:
					del self._last_update_state[state_key]
		
	def on_master_volume_change(self, value):
		"""Handle master volume change with dB calculation"""
		volume_percent = float(value)
	
		# Calculate dB value based on position
		if volume_percent == 0:
			db_value = -60.0
			linear_gain = 0.001  # Essentially muted
		elif volume_percent <= 75:
			# 0% to 75% maps to -60dB to 0dB
			db_value = -60.0 + (volume_percent / 75.0) * 60.0
			linear_gain = 10.0 ** (db_value / 20.0)
		else:
			# 75% to 100% maps to 0dB to +9dB
			db_value = ((volume_percent - 75.0) / 25.0) * 9.0
			linear_gain = 10.0 ** (db_value / 20.0)
	
		# Update audio engine
		self.audio_engine.set_master_volume(linear_gain)

	def adjust_bpm(self, delta):
		"""Adjust BPM by delta amount and update text box"""
		new_bpm = self.audio_engine.bpm + delta
		self.audio_engine.set_bpm(new_bpm)
		self.bpm_var.set(str(self.audio_engine.bpm))
		
	def on_bpm_entry_change(self, event=None):
		"""Handle BPM entry text box changes"""
		try:
			bpm_text = self.bpm_var.get().strip()
			bpm_value = int(bpm_text)
			
			# Validate BPM range (60-200)
			if bpm_value < 60:
				bpm_value = 60
			elif bpm_value > 200:
				bpm_value = 200
			
			# Update audio engine
			self.audio_engine.set_bpm(bpm_value)
			
			# Update text box to show validated value
			self.bpm_var.set(str(bpm_value))
			
		except ValueError:
			# Invalid input - reset to current BPM
			self.bpm_var.set(str(self.audio_engine.bpm))
		
	def populate_device_lists(self):
		"""Populate device combo boxes and select currently used devices"""
		input_devices = self.audio_engine.get_input_devices()
		output_devices = self.audio_engine.get_output_devices()
	
		input_names = [f"{dev['name']}" for dev in input_devices]
		output_names = [f"{dev['name']}" for dev in output_devices]
	
		self.input_device_combo['values'] = input_names
		self.output_device_combo['values'] = output_names
	
		# Select currently used devices by the audio engine
		try:
			# Find the currently selected input device
			input_selection = 0  # fallback to first
			current_input_idx = self.audio_engine.input_device
			if current_input_idx is not None:
				for i, device in enumerate(input_devices):
					if device['index'] == current_input_idx:
						input_selection = i
						break
		
			# Find the currently selected output device
			output_selection = 0  # fallback to first
			current_output_idx = self.audio_engine.output_device
			if current_output_idx is not None:
				for i, device in enumerate(output_devices):
					if device['index'] == current_output_idx:
						output_selection = i
						break
		
			if input_names:
				self.input_device_combo.current(input_selection)
				self.on_input_device_change()
			
			if output_names:
				self.output_device_combo.current(output_selection)
				self.on_output_device_change()
			
		except Exception as e:
			print(f"Error setting current devices: {e}")
			# Fallback to first device if current device detection fails
			if input_names:
				self.input_device_combo.current(0)
				self.on_input_device_change()
			
			if output_names:
				self.output_device_combo.current(0)
				self.on_output_device_change()
			
	def on_input_device_change(self, event=None):
		"""Handle input device selection change"""
		selection = self.input_device_combo.current()
		if selection >= 0:
			input_devices = self.audio_engine.get_input_devices()
			if selection < len(input_devices):
				device_index = input_devices[selection]['index']
				success = self.audio_engine.set_input_device(device_index)
				if success:
					# Restart stream to apply device change
					self.restart_audio_stream()
				else:
					print(f"Failed to set input device to index {device_index}")
				
	def on_output_device_change(self, event=None):
		"""Handle output device selection change"""
		selection = self.output_device_combo.current()
		if selection >= 0:
			output_devices = self.audio_engine.get_output_devices()
			if selection < len(output_devices):
				device_index = output_devices[selection]['index']
				success = self.audio_engine.set_output_device(device_index)
				if success:
					# Restart stream to apply device change
					self.restart_audio_stream()
				else:
					print(f"Failed to set output device to index {device_index}")

	def restart_audio_stream(self):
		"""Restart audio stream to apply device changes"""
		try:
			was_playing = self.audio_engine.is_playing
			was_recording = self.audio_engine.is_recording
			
			# Stop current stream
			self.audio_engine.stop_stream()
			
			# Start new stream with new devices
			if self.audio_engine.start_stream():
				print("Audio stream restarted with new devices")
				
				# Resume playback if it was active
				if was_playing:
					self.audio_engine.is_playing = True
			else:
				print("Failed to restart audio stream")
				
		except Exception as e:
			print(f"Error restarting audio stream: {e}")
				
	def save_project(self):
		"""Save current project"""
		project_name = self.project_name_display.cget('text')
		if project_name.strip():
			filename = self.project_manager.save_project(
				self.track_manager, 
				self.audio_engine, 
				project_name
			)
			if filename:
				messagebox.showinfo("Project Saved", f"Project saved successfully!")
			else:
				messagebox.showerror("Save Error", "Failed to save project.")
		else:
			messagebox.showwarning("No Project Name", "Project has no name.")
			
	def load_project(self):
		"""Load an existing project with audio files"""
		projects = self.project_manager.get_project_list()
		
		if not projects:
			messagebox.showinfo("No Projects", "No saved projects found.")
			return
			
		# Create selection dialog
		dialog = tk.Toplevel(self.root)
		dialog.title("Load Project")
		dialog.geometry("400x300")
		dialog.configure(bg=self.colors['upper_bg'])
		dialog.transient(self.root)
		dialog.grab_set()
		
		tk.Label(dialog, text="Select Project to Load:", font=('Arial', 12, 'bold'), 
				bg=self.colors['upper_bg'], fg=self.colors['fg']).pack(pady=10)
		
		listbox = tk.Listbox(dialog, font=('Arial', 10), height=10)
		for project in projects:
			display_text = f"{project['name']}"
			listbox.insert(tk.END, display_text)
		listbox.pack(pady=10, padx=20, fill='both', expand=True)
		
		button_frame = tk.Frame(dialog, bg=self.colors['upper_bg'])
		button_frame.pack(pady=10)
		
		def on_load():
			selection = listbox.curselection()
			if selection:
				selected_index = selection[0]
				selected_project_data = projects[selected_index]
		
				# Load project metadata first
				if self.project_manager.load_project(selected_project_data['file']):
					# Load actual audio files first
					self.audio_engine.load_project_audio_files(selected_project_data['name'])
					
					# Then apply project settings to managers
					self.project_manager.apply_project_to_managers(self.track_manager, self.audio_engine)
					
					# Sync track states - make sure track manager knows which tracks have data
					for track_num in range(1, 9):
						track = self.track_manager.get_track(track_num)
						if track:
							has_audio_data = self.audio_engine.has_track_data(track_num)
							track.set_has_data(has_audio_data)
							if has_audio_data:
								print(f"✓ Track {track_num} has audio data and is {'muted' if track.is_muted else 'unmuted'}")
					
					# Update recordings directory
					recordings_folder = self.project_manager.set_project_name(selected_project_data['name'])
					self.audio_engine.set_recordings_directory(recordings_folder)
			
					# Update UI
					self.project_name_display.config(text=selected_project_data['name'])
			
					self.bpm_var.set(str(self.audio_engine.bpm))

					# Update metronome button state
					if self.audio_engine.metronome_enabled:
						self.metronome_button.config(text="ON", bg=self.colors['button_playing'])
					else:
						self.metronome_button.config(text="OFF", bg=self.colors['button_normal'])
			
					# Update track names from loaded project
					for track_num in range(1, 9):
						track = self.track_manager.get_track(track_num)
						widgets = self.track_widgets.get(track_num)
						if track and widgets:
							widgets['track_name_var'].set(track.name)
			
					# Update volume fader labels and values
					self.update_track_name_labels()
					for track_num in range(1, 9):
						track = self.track_manager.get_track(track_num)
						if track and track_num in self.volume_faders:
							# Set fader to saved volume
							self.volume_faders[track_num].set(int(track.volume * 100))
			
					# Update FX button states
					for track_num in range(1, 9):
						fx_type = self.audio_engine.get_track_fx(track_num)
						if track_num in self.fx_buttons:
							fx_button = self.fx_buttons[track_num]
							if fx_type == "none":
								fx_button.config(bg=self.colors['fx_button'])
							else:
								fx_button.config(bg=self.colors['fx_active'])
			
					# Clear ALL caches to force complete UI refresh
					self.clear_ui_caches()
			
					# Force immediate UI update for all tracks
					for track_num in range(1, 9):
						self.update_track_ui_optimized(track_num)
			
					messagebox.showinfo("Project Loaded", f"Project '{selected_project_data['name']}' loaded successfully!")
					dialog.destroy()
				else:
					messagebox.showerror("Load Error", "Failed to load project.")
		def on_cancel():
			dialog.destroy()
		
		tk.Button(button_frame, text="Load", command=on_load, **{
			'font': ('Arial', 10, 'bold'), 'bg': self.colors['button_normal'], 
			'fg': self.colors['fg'], 'width': 8
		}).pack(side='left', padx=5)
		
		tk.Button(button_frame, text="Cancel", command=on_cancel, **{
			'font': ('Arial', 10, 'bold'), 'bg': self.colors['button_normal'], 
			'fg': self.colors['fg'], 'width': 8
		}).pack(side='left', padx=5)


	def sync_track_states_after_load(self):
		"""Synchronize track states after loading project"""
		for track_num in range(1, 9):
			track = self.track_manager.get_track(track_num)
			if not track:
				continue
			
			# Check if audio engine has data for this track
			has_audio_data = self.audio_engine.has_track_data(track_num)
			track.set_has_data(has_audio_data)
		
			# Force UI state update by clearing cache
			state_key = f'track_{track_num}_state'
			if state_key in self._last_update_state:
				del self._last_update_state[state_key]
		
			print(f"Track {track_num}: has_data={has_audio_data}, muted={track.is_muted}, name='{track.name}'")
	
	def sync_track_states_after_load(self):
		"""Synchronize track states after loading project"""
		for track_num in range(1, 9):
			track = self.track_manager.get_track(track_num)
			if not track:
				continue
			
			# Check if audio engine has data for this track
			has_audio_data = self.audio_engine.has_track_data(track_num)
			track.set_has_data(has_audio_data)
		
			# Force UI state update by clearing cache
			state_key = f'track_{track_num}_state'
			if state_key in self._last_update_state:
				del self._last_update_state[state_key]
		
			print(f"Track {track_num}: has_data={has_audio_data}, muted={track.is_muted}, name='{track.name}'")

	def clear_ui_caches(self):
		"""Clear all UI caches for performance optimization"""
		self._level_cache.clear()
		self._cursor_cache.clear()
		self._waveform_cache.clear()
		self._segment_cache.clear()
		self._last_update_state.clear()
		print("✓ UI caches cleared")
		
	def stop_all(self):
		"""Stop both playback and recording, disarm all tracks"""
		# Stop recording if active
		if self.is_recording:
			filename = self.audio_engine.stop_recording()
			self.is_recording = False
			
			# Mark track as having data
			armed_track = self.track_manager.get_armed_track()
			if armed_track and filename:
				self.track_manager.mark_track_has_data(armed_track, True)
				# Clear waveform cache to force redraw
				cache_key = f'waveform_{armed_track}'
				self._waveform_cache.discard(cache_key)
		
		# Stop playback
		self.audio_engine.stop_playback()
		self.is_playing = False
		self.play_button.config(text="PLAY", bg=self.colors['button_normal'], state='normal')
		
		# Disarm all tracks
		self.track_manager.disarm_all_tracks()
		
		# Clear all waveform cursors
		for track_num in range(1, 9):
			widgets = self.track_widgets.get(track_num)
			if widgets:
				widgets['waveform_canvas'].delete('cursor')
		
		# Clear cursor cache
		self._cursor_cache.clear()
	
	def draw_level_meter_optimized(self, canvas, level):
		"""Optimized level meter - only update changed segments"""
		width = 50
		height = 20
		num_segments = 8
		segment_width = (width - 2) / num_segments
		segment_height = height - 4
		
		scaled_level = min(1.0, level / 0.95)
		active_segments = int(scaled_level * num_segments)
		
		# Check if we need to redraw (cache the last active segment count)
		cache_key = f'segments_{id(canvas)}'
		last_active = self._segment_cache.get(cache_key, -1)
		if last_active == active_segments:
			return  # No change needed
		
		self._segment_cache[cache_key] = active_segments
		
		# Only clear and redraw if segments changed
		canvas.delete("all")
		
		for i in range(num_segments):
			x1 = 1 + i * segment_width
			x2 = x1 + segment_width - 1
			y1 = 2
			y2 = y1 + segment_height
			
			if i < active_segments:
				if i < num_segments * 0.7:
					color = '#00ff00'
				elif i < num_segments * 0.9:
					color = '#ffff00'
				else:
					color = '#ff0000'
			else:
				color = '#333333'
				
			canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline='#666666')
			
	def draw_peak_indicator(self, peak_label, peak_active):
		"""Update peak indicator label"""
		if peak_active:
			peak_label.config(fg='#ff0000', bg='#440000')  # Bright red on dark red
		else:
			peak_label.config(fg='#333333', bg='#2F4F4F')  # Dark gray with dark teal background
			
	def draw_waveform_cached(self, canvas, track_num):
		"""Draw waveform with better caching"""
		cache_key = f'waveform_{track_num}'
		
		# Check if we already have this waveform cached
		if cache_key in self._waveform_cache:
			return  # Already drawn
		
		# Draw the waveform
		self.draw_waveform(canvas, track_num)
		self._waveform_cache.add(cache_key)
		
	def draw_waveform(self, canvas, track_num):
		"""Draw waveform for a track"""
		canvas.delete("all")
		
		# Check if track has data
		if not self.audio_engine.has_track_data(track_num):
			# Draw "No Recording" text
			canvas.create_text(
				150, 17,  # Center of 300x35 canvas
				text="No Recording",
				fill='#666666',
				font=('Arial', 10)
			)
			return
		
		# Get track data
		track_data = self.audio_engine.track_data.get(track_num)
		if track_data is None or len(track_data) == 0:
			return
			
		canvas_width = 300
		canvas_height = 35
		
		# Downsample audio data for display
		samples_per_pixel = max(1, len(track_data) // canvas_width)
		downsampled = []
		
		for i in range(0, len(track_data), samples_per_pixel):
			chunk = track_data[i:i + samples_per_pixel]
			if len(chunk) > 0:
				# Use RMS for better visual representation
				rms = np.sqrt(np.mean(chunk ** 2))
				downsampled.append(rms)
		
		if len(downsampled) == 0:
			return
			
		# Normalize to canvas height
		max_level = max(downsampled) if max(downsampled) > 0 else 1
		center_y = canvas_height // 2
		
		# Draw waveform
		for i, level in enumerate(downsampled):
			x = (i * canvas_width) // len(downsampled)
			y_offset = (level / max_level) * (center_y - 2)
			
			# Draw vertical line for waveform
			canvas.create_line(
				x, center_y - y_offset, 
				x, center_y + y_offset, 
				fill='#00ff88', 
				width=1
			)
				
	def update_waveform_cursor_optimized(self, track_num, widgets):
		"""Update waveform cursor - only if position changed significantly"""
		track_length = self.audio_engine.track_lengths.get(track_num, 0)
		if track_length == 0:
			return
		
		position = self.audio_engine.playback_position
		canvas_width = 300
		cursor_x = (position / track_length) * canvas_width
		
		# Only update cursor if moved by at least 2 pixels
		cache_key = f'cursor_{track_num}'
		last_x = self._cursor_cache.get(cache_key, -999)
		if abs(cursor_x - last_x) > 2:  # Only update if moved significantly
			self._cursor_cache[cache_key] = cursor_x
			
			canvas = widgets['waveform_canvas']
			canvas.delete('cursor')
			canvas.create_line(cursor_x, 0, cursor_x, 35, fill='#ffffff', width=2, tags='cursor')
				
	def start_playback(self):
		"""Start playback - start recording if track is armed"""
		if self.audio_engine.start_playback():
			self.is_playing = True
			self.play_button.config(text="PLAYING", bg=self.colors['button_playing'], state='disabled')
			print("Playback started")
			
			# If a track is armed, also start recording
			armed_track = self.track_manager.get_armed_track()
			if armed_track is not None:
				if self.audio_engine.start_recording(armed_track):
					self.is_recording = True
					print(f"Recording started to track {armed_track}")
				else:
					messagebox.showerror("Audio Error", "Failed to start recording. Check audio devices.")
		else:
			messagebox.showerror("Audio Error", "Failed to start playback. Check audio devices.")
			
	def toggle_arm(self, track_num):
		"""Toggle track arm state"""
		current_armed = self.track_manager.get_armed_track()
		
		if current_armed == track_num:
			# Disarm if already armed
			self.track_manager.disarm_all_tracks()
		else:
			# Arm this track (only if it doesn't have data)
			track = self.track_manager.get_track(track_num)
			if track and not track.has_data:
				self.track_manager.arm_track(track_num)
			
	def toggle_mute(self, track_num):
		"""Toggle track mute"""
		self.track_manager.toggle_track_mute(track_num)
		
	def clear_track(self, track_num):
		"""Clear track after confirmation"""
		track = self.track_manager.get_track(track_num)
		if track and track.has_data:
			result = messagebox.askyesno(
				"Clear Track", 
				f"Are you sure you want to clear Track {track_num}?\nThis will also delete the associated audio file and cannot be undone."
			)
			if result:
				# Clear track and delete associated files
				self.track_manager.clear_track(track_num)
				self.audio_engine.clear_track(track_num)
				
				# Clear caches for this track
				cache_key = f'waveform_{track_num}'
				self._waveform_cache.discard(cache_key)
				
				state_key = f'track_{track_num}_state'
				if state_key in self._last_update_state:
					del self._last_update_state[state_key]
				
	def toggle_metronome(self):
		"""Toggle metronome on/off"""
		if self.audio_engine.metronome_enabled:
			self.audio_engine.set_metronome(False)
			self.metronome_button.config(text="OFF", bg=self.colors['button_normal'])
		else:
			self.audio_engine.set_metronome(True)
			self.metronome_button.config(text="ON", bg=self.colors['button_playing'])
			
	def on_metronome_volume_change(self, value):
		"""Handle metronome volume change"""
		volume = int(value) / 100.0  # Convert to 0.0-1.0 range
		self.audio_engine.set_metronome_volume(volume)
	
	def start_optimized_ui_update_thread(self):
		"""Start OPTIMIZED background threads for UI updates"""
		
		# Main UI update thread (10Hz) - for buttons, status, waveforms, cursors
		def main_update_loop():
			frame_count = 0
			
			while True:
				try:
					frame_count += 1
					# Stagger track updates - only update 2 tracks per frame for 8 total tracks
					tracks_to_update = [(frame_count % 4) * 2 + i + 1 for i in range(2)]
					
					self.root.after(0, lambda ttu=tracks_to_update: self.update_ui_optimized(ttu))
					time.sleep(0.1)  # 10Hz - for main UI elements
				except:
					break
		
		# Level meter update thread (20Hz) - faster updates for level meters only
		def level_meter_update_loop():
			while True:
				try:
					self.root.after(0, self.update_all_level_meters)
					time.sleep(0.05)  # 20Hz - 2x faster for level meters
				except:
					break
					
		# Start both threads
		main_thread = threading.Thread(target=main_update_loop, daemon=True)
		level_thread = threading.Thread(target=level_meter_update_loop, daemon=True)
		
		main_thread.start()
		level_thread.start()
	
	def update_all_level_meters(self):
		"""Update all level meters at 20Hz for responsive feedback"""
		try:
			for track_num in range(1, 9):
				widgets = self.track_widgets.get(track_num)
				if widgets:
					self.update_level_meter_optimized(track_num, widgets)
		except Exception as e:
			pass  # Silently handle any errors in level meter updates
		
	def update_ui_optimized(self, tracks_to_update):
		"""OPTIMIZED UI update - only update what changed"""
		try:
			# Update time display only if playing
			if self.is_playing:
				playback_time = self.audio_engine.get_playback_time()
				time_str = self.format_time_with_ms(playback_time)
				self.time_label.config(text=time_str)
			
			# Update only specific tracks this frame
			for track_num in tracks_to_update:
				if track_num <= 8:
					self.update_track_ui_optimized(track_num)
					
		except Exception as e:
			print(f"UI update error: {e}")
			
	def format_time_with_ms(self, seconds):
		"""Format time as MM:SS.mmm"""
		minutes = int(seconds // 60)
		secs = int(seconds % 60)
		milliseconds = int((seconds % 1) * 1000)
		return f"{minutes:02d}:{secs:02d}.{milliseconds:03d}"
		
	def update_track_ui_optimized(self, track_num):
		"""OPTIMIZED track UI update - only what changed"""
		track = self.track_manager.get_track(track_num)
		widgets = self.track_widgets.get(track_num)
		
		if not track or not widgets:
			return
		
		# Create state hash to detect changes
		current_state = (
			track.name,
			track.is_armed,
			track.is_muted,
			track.has_data,
			self.is_playing,
			self.is_recording
		)
		
		state_key = f'track_{track_num}_state'
		last_state = self._last_update_state.get(state_key)
		
		# Only update if state changed
		if last_state != current_state:
			self._last_update_state[state_key] = current_state
			
			# Update track name entry only if changed
			if last_state is None or last_state[0] != track.name:
				widgets['track_name_var'].set(track.name)
			
			# Update ARM button only if state changed
			if last_state is None or last_state[1] != track.is_armed or last_state[3] != track.has_data:
				if track.has_data:
					widgets['arm_button'].config(
						bg=self.colors['button_disabled'],
						fg='#888888',
						text="DISABLED",
						state='disabled'
					)
				else:
					widgets['arm_button'].config(state='normal', fg=self.colors['fg'])
					if track.is_armed:
						widgets['arm_button'].config(bg=self.colors['button_armed'], text="ARMED")
					else:
						widgets['arm_button'].config(bg=self.colors['button_normal'], text="ARM")
			
			# Update MUTE button only if changed
			if last_state is None or last_state[2] != track.is_muted:
				color = self.colors['button_muted'] if track.is_muted else self.colors['button_normal']
				widgets['mute_button'].config(bg=color)
			
			# Update waveform only if track data changed
			if last_state is None or last_state[3] != track.has_data:
				if track.has_data:
					self.draw_waveform_cached(widgets['waveform_canvas'], track_num)
				else:
					widgets['waveform_canvas'].delete("all")
					widgets['waveform_canvas'].create_text(
						150, 17, text="No Recording", fill='#666666', font=('Arial', 10)
					)
			
			# Update status label only if state changed
			status_text = self.get_status_from_state(current_state)
			if last_state is None or self.get_status_from_state(last_state) != status_text:
				widgets['status_label'].config(text=status_text)
		
		# Always update level meters and cursors (but optimize them)
		# Note: Level meters now updated by separate 20Hz thread
		
		# Update cursors only during playback and only for tracks with data
		if self.is_playing and track.has_data:
			self.update_waveform_cursor_optimized(track_num, widgets)
	
	def get_status_from_state(self, state):
		"""Helper to get status text from state tuple"""
		name, is_armed, is_muted, has_data, is_playing, is_recording = state
		status_text = "Recorded" if has_data else "Empty"
		if is_muted and has_data:
			status_text += " (Muted)"
		elif is_armed and not has_data:
			status_text += " (Recording)" if is_recording else " (Armed)"
		return status_text
	
	def update_level_meter_optimized(self, track_num, widgets):
		"""Update level meter only if level changed significantly"""
		level = self.audio_engine.get_track_level(track_num)
		peak = self.audio_engine.get_track_peak(track_num)
		
		# Check if we have cached level info
		cache_key = f'level_{track_num}'
		cached_level = self._level_cache.get(cache_key, -1)
		
		# Only redraw if level changed by more than 5% or peak state changed
		peak_cache_key = f'peak_{track_num}'
		cached_peak = self._level_cache.get(peak_cache_key, not peak)
		
		if abs(level - cached_level) > 0.05 or peak != cached_peak:
			self._level_cache[cache_key] = level
			self._level_cache[peak_cache_key] = peak
			
			self.draw_level_meter_optimized(widgets['level_canvas'], level)
			self.draw_peak_indicator(widgets['peak_indicator'], peak)

	def setup_focus_handling(self):
		"""Setup focus handling to hide text cursors when clicking elsewhere"""
		def hide_text_cursors(event):
			# Only hide cursors if we didn't click on an Entry widget
			if not isinstance(event.widget, tk.Entry):
				self.root.focus_set()  # Remove focus from any Entry widgets
	
		# Bind to root window and all frames
		self.root.bind("<Button-1>", hide_text_cursors)
		for widget in self.root.winfo_children():
			if isinstance(widget, tk.Frame):
				widget.bind("<Button-1>", hide_text_cursors)