#!/usr/bin/env python3
"""
Simple Multitrack Recorder
Main application entry point
"""

import tkinter as tk
import sys
import os
import threading
import time
from pathlib import Path
from PIL import Image, ImageTk, ImageEnhance

# Add current directory to path for imports
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

from ui_controller import MultitrackUI
from audio_engine import AudioEngine
from track_manager import TrackManager
from project_manager import ProjectManager

class MultitrackRecorderApp:
	def __init__(self):
		self.root = tk.Tk()
		self.setup_window()
		
		# Initialize core components
		self.audio_engine = AudioEngine()
		self.track_manager = TrackManager()
		self.project_manager = ProjectManager()
		
		# Set track manager reference in audio engine for mute/solo functionality
		self.audio_engine.set_track_manager(self.track_manager)
		
		# Initialize UI with component references
		self.ui = MultitrackUI(
			self.root, 
			self.audio_engine, 
			self.track_manager,
			self.project_manager
		)
		
		# Setup cleanup on close
		#self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
		
	def setup_window(self):
		self.root.title("Clif's 8track")
		self.root.geometry("1500x900")  # Wider for waveform display
		self.root.configure(bg='#008080')  # Teal background
		
		# Try to load and set deer background image
		try:
			# Function to get the correct path for bundled files
			def get_resource_path(relative_path):
				"""Get absolute path to resource, works for dev and for PyInstaller"""
				try:
					# PyInstaller creates a temp folder and stores path in _MEIPASS
					base_path = sys._MEIPASS
				except AttributeError:
					base_path = os.path.abspath(".")
				return os.path.join(base_path, relative_path)
			
			deer_image_path = get_resource_path("deer.jpg")
			if os.path.exists(deer_image_path):
				print("deer.jpg found, loading as background...")
				# Load and resize image to fit window
				pil_image = Image.open(deer_image_path)
				pil_image = pil_image.resize((1500, 900), Image.Resampling.LANCZOS)
				
				# Convert to PhotoImage
				self.bg_image = ImageTk.PhotoImage(pil_image)
				
				# Create background label
				bg_label = tk.Label(self.root, image=self.bg_image)
				bg_label.place(x=0, y=0, relwidth=1, relheight=1)
				
				print("Background image deer.jpg loaded successfully")
			else:
				print("deer.jpg not found")
		except Exception as e:
			print(f"Could not load background image: {e}")
	
		# Make window not resizable for consistency
		self.root.resizable(False, False)
		
		# Position window to the left of screen instead of centering
		self.root.update_idletasks()
		x = 50  # 50 pixels from left edge
		y = (self.root.winfo_screenheight() // 2) - (900 // 2)  # Still center vertically
		self.root.geometry(f"1500x900+{x}+{y}")
		
	def run(self):
		"""Start the application"""
		try:
			print("Starting Multitrack Recorder...")
			self.audio_engine.initialize()
			print("Audio engine initialized")
		
			# Show startup calibration popup
			self.show_startup_calibration()
		
			self.root.mainloop()
		except Exception as e:
			print(f"Error starting application: {e}")
			self.cleanup()

	def show_startup_calibration(self):
		"""Show calibration popup during startup"""
		try:
			# Create calibration popup
			self.calibration_popup = tk.Toplevel(self.root)
			self.calibration_popup.title("Calibrating")
			self.calibration_popup.geometry("350x140")
			self.calibration_popup.configure(bg='#2F4F4F')
			self.calibration_popup.transient(self.root)
			self.calibration_popup.grab_set()
			self.calibration_popup.resizable(False, False)
		
			# Center the popup
			self.calibration_popup.update_idletasks()
			x = (self.calibration_popup.winfo_screenwidth() // 2) - (350 // 2)
			y = (self.calibration_popup.winfo_screenheight() // 2) - (140 // 2)
			self.calibration_popup.geometry(f"350x140+{x}+{y}")
		
			# Popup content
			tk.Label(
				self.calibration_popup,
				text="Calibrating...",
				font=('Arial', 16, 'bold'),
				bg='#2F4F4F',
				fg='#ffffff'
			).pack(pady=15)
		
			tk.Label(
				self.calibration_popup,
				text="Measuring audio system latency.",
				font=('Arial', 11),
				bg='#2F4F4F',
				fg='#ffffff'
			).pack()
		
			tk.Label(
				self.calibration_popup,
				text="Please wait a moment...",
				font=('Arial', 11),
				bg='#2F4F4F',
				fg='#ffffff'
			).pack(pady=(0, 10))
		
			self.calibration_popup.update()
		
			# Start calibration in background
			def calibration_thread():
				try:
					time.sleep(1)  # Brief delay
					self.audio_engine.measure_latency()
					# Close popup in main thread
					self.root.after(0, self.close_startup_calibration)
				except Exception as e:
					print(f"Startup calibration failed: {e}")
					self.root.after(0, self.close_startup_calibration)
		
			threading.Thread(target=calibration_thread, daemon=True).start()
			
		except Exception as e:
			print(f"Could not show calibration popup: {e}")

	def close_startup_calibration(self):
		"""Close the startup calibration popup"""
		try:
			if hasattr(self, 'calibration_popup'):
				self.calibration_popup.destroy()
				delattr(self, 'calibration_popup')
		except:
			pass
			
		def on_closing(self):
			"""Handle application shutdown"""
			self.cleanup()
			self.root.destroy()
		
		def cleanup(self):
			"""Clean up resources"""
			try:
				if hasattr(self, 'audio_engine'):
					self.audio_engine.cleanup()
				print("Application cleaned up successfully")
			except Exception as e:
				print(f"Error during cleanup: {e}")

if __name__ == "__main__":
	app = MultitrackRecorderApp()
	app.run()