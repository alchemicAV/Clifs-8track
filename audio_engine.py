"""
Audio Engine - Handles all recording and playback operations
UPDATED VERSION with volume control, FX processing, MP3 export, and improved latency calibration
"""

import sounddevice as sd
import soundfile as sf
import numpy as np
import threading
import time
import os
from pathlib import Path
from queue import Queue

class SimpleCompressor:
	"""Simple peak-limiting compressor with proper gain reduction"""
	def __init__(self, threshold=0.8, ratio=10.0, attack_ms=5.0, release_ms=50.0, sample_rate=44100):
		self.threshold = threshold
		self.ratio = ratio
		self.attack_coeff = np.exp(-1.0 / (attack_ms * 0.001 * sample_rate))
		self.release_coeff = np.exp(-1.0 / (release_ms * 0.001 * sample_rate))
		self.envelope = 0.0
		
	def process(self, audio):
		"""Process audio through compressor"""
		if len(audio) == 0:
			return audio
			
		output = np.zeros_like(audio)
		
		for i in range(len(audio)):
			# Get input level (absolute value)
			input_level = abs(audio[i])
			
			# Update envelope follower (peak detector)
			target_envelope = input_level
			if target_envelope > self.envelope:
				self.envelope += (target_envelope - self.envelope) * (1.0 - self.attack_coeff)
			else:
				self.envelope += (target_envelope - self.envelope) * (1.0 - self.release_coeff)
			
			# Calculate gain reduction
			gain = 1.0  # Default no reduction
			if self.envelope > self.threshold:
				# Amount over threshold
				over_amount = self.envelope - self.threshold
				# Compressed amount
				compressed_amount = over_amount / self.ratio
				# Target output level
				target_level = self.threshold + compressed_amount
				# Gain needed to achieve target
				if self.envelope > 0:
					gain = target_level / self.envelope
			
			# Apply gain with makeup gain (compensate for level loss)
			makeup_gain = 1.0 + (1.0 - 1.0/self.ratio) * (self.threshold / 1.0)
			output[i] = audio[i] * gain * makeup_gain
		
		return output

class SimpleReverb:
	"""Simple delay-based reverb"""
	def __init__(self, room_size=0.7, damping=0.5, wet=0.3, sample_rate=44100):
		self.wet = wet
		self.dry = 1.0 - wet
		
		# Delay line lengths for different room sizes
		if room_size > 0.8:  # Large hall
			delay_times = [0.089, 0.11, 0.127, 0.135, 0.22, 0.254]  # 30-127ms delays
			self.wet = 0.4
		else:  # Small room
			delay_times = [0.015, 0.023, 0.035, 0.047]  # 15-47ms delays
			self.wet = 0.5
		
		self.dry = 1.0 - self.wet
		
		# Create delay lines
		self.delay_lines = []
		self.feedback_gains = [0.7, 0.6, 0.5, 0.4]
		
		for delay_time, fb_gain in zip(delay_times, self.feedback_gains):
			delay_samples = int(delay_time * sample_rate)
			self.delay_lines.append({
				'buffer': np.zeros(delay_samples),
				'index': 0,
				'feedback': fb_gain * (1.0 - damping)
			})
	
	def process(self, audio):
		"""Process audio through reverb"""
		if len(audio) == 0:
			return audio
			
		output = np.zeros_like(audio)
		
		for i in range(len(audio)):
			wet_sum = 0.0
			
			# Process each delay line
			for delay_line in self.delay_lines:
				buffer = delay_line['buffer']
				idx = delay_line['index']
				feedback = delay_line['feedback']
				
				# Get delayed sample
				delayed = buffer[idx]
				wet_sum += delayed
				
				# Write new sample with feedback
				buffer[idx] = audio[i] + delayed * feedback
				
				# Advance delay line index
				delay_line['index'] = (idx + 1) % len(buffer)
			
			# Mix dry and wet signals
			output[i] = audio[i] * self.dry + wet_sum * self.wet * 0.25  # Scale down wet sum
		
		return output

class AudioEngine:
	def __init__(self):
		self.sample_rate = 44100
		self.channels = 1  # Mono input
		self.dtype = np.float32
		self.buffer_size = 256  # Reduced from 1024 for lower latency
		
		# Device selection
		self.input_device = None
		self.output_device = None
		self.available_input_devices = []
		self.available_output_devices = []
		
		# Track manager reference (will be set externally)
		self.track_manager = None
		
		# Project-specific recordings directory
		self.recordings_dir = Path("recordings") / "Default Project"
		
		# Recording state
		self.is_recording = False
		self.recording_track = None
		self.recording_buffer = []
		self.recording_lock = threading.Lock()
		
		# Playback state
		self.is_playing = False
		self.playback_position = 0
		self.playback_start_time = 0
		self.playback_lock = threading.Lock()
		
		# Track data storage
		self.track_data = {}  # {track_num: numpy array}
		self.track_lengths = {}  # {track_num: length in samples}
		
		# Track volume and FX settings
		self.track_volumes = {}  # {track_num: volume (0.0-1.0)}
		self.track_fx = {}       # {track_num: fx_type}
		self.fx_processors = {}  # {track_num: {'compressor': obj, 'reverb': obj}}
		
		# Initialize track settings
		for i in range(1, 9):
			self.track_volumes[i] = 0.75  # Default 75%
			self.track_fx[i] = "none"
			self.fx_processors[i] = {}
		
		# Volume monitoring with decay for better visualization
		self.track_levels = {}  # {track_num: current level}
		self.track_peaks = {}   # {track_num: peak detected}
		self.level_decay = 0.85  # Faster decay for more responsive meters
		self.peak_hold_time = {}  # {track_num: time when peak was detected}
		self.peak_hold_duration = 1.0  # Hold peak indicator for 1 second
		
		# Latency compensation
		self.measured_latency_samples = 0
		self.measured_latency_ms = 0.0
		self.latency_calibrated = False
		
		# Initialize all tracks to zero levels
		for i in range(1, 9):
			self.track_levels[i] = 0.0
			self.track_peaks[i] = False
			self.peak_hold_time[i] = 0.0
		
		# Audio stream
		self.stream = None
		
		# Metronome
		self.metronome_enabled = False
		self.metronome_volume = 0.5  # Default 50%
		self.bpm = 120
		self.beat_counter = 0
		self.samples_per_beat = 0
		self.metronome_sound = None
		self.metronome_and_sound = None  # For "and" beats (every 4th)
		self.current_beat_in_measure = 1  # Track which beat in 4/4 time
		
		self.initialize_devices()
		self.initialize_metronome()
		
		self.calculate_metronome_timing()

		self.master_volume_gain = 1.0  # Default 0 dB (75% slider position)
		
	def set_track_manager(self, track_manager):
		"""Set track manager reference for mute/solo functionality"""
		self.track_manager = track_manager
		track_manager._audio_engine_ref = self

	def set_master_volume(self, linear_gain):
		"""Set master volume as linear gain factor"""
		self.master_volume_gain = max(0.001, min(10.0, linear_gain))  # Clamp reasonable range
		
	def set_track_volume(self, track_num, volume):
		"""Set volume for a track (0.0 to 1.0)"""
		self.track_volumes[track_num] = max(0.0, min(1.0, volume))
		
	def get_track_volume(self, track_num):
		"""Get volume for a track"""
		return self.track_volumes.get(track_num, 0.75)
		
	def set_track_fx(self, track_num, fx_type):
		"""Set FX type for a track"""
		self.track_fx[track_num] = fx_type
		
		# Initialize FX processors based on type
		if fx_type == "wide_hall":
			self.fx_processors[track_num] = {
				'compressor': SimpleCompressor(threshold=0.7, ratio=3.0),
				'reverb': SimpleReverb(room_size=0.9, wet=0.4)
			}
		elif fx_type == "studio":
			self.fx_processors[track_num] = {
				'compressor': SimpleCompressor(threshold=0.6, ratio=4.0),
				'reverb': SimpleReverb(room_size=0.5, wet=0.25)
			}
		elif fx_type == "compressor":
			self.fx_processors[track_num] = {
				'compressor': SimpleCompressor(threshold=0.5, ratio=6.0)
			}
		else:  # "none"
			self.fx_processors[track_num] = {}
			
	def get_track_fx(self, track_num):
		"""Get current FX type for a track"""
		return self.track_fx.get(track_num, "none")
		
	def process_track_fx(self, track_num, audio_data):
		"""Process audio through track FX chain"""
		if track_num not in self.fx_processors or not self.fx_processors[track_num]:
			return audio_data
	
		processed = audio_data.copy()
		processors = self.fx_processors[track_num]
	
		# Apply compression first
		if 'compressor' in processors:
			processed = processors['compressor'].process(processed)
	
		# Then apply reverb
		if 'reverb' in processors:
			processed = processors['reverb'].process(processed)
	
		return processed

	def initialize(self):
		"""Initialize audio system and find USB microphone"""
		try:
			self.find_usb_microphone()
			print("Audio engine initialized successfully")
			return True
		except Exception as e:
			print(f"Failed to initialize audio engine: {e}")
			return False
	
	def auto_calibrate_latency(self):
		"""Auto-calibrate latency in background with popup"""
		time.sleep(2)  # Wait for UI to load
	
		# This will be called from main thread to show popup
		def show_calibration_popup():
			try:
				import tkinter as tk
				from tkinter import ttk
			
				# Get the root window (assume it's available globally)
				root = None
				for obj in globals().values():
					if hasattr(obj, 'root') and hasattr(obj.root, 'title'):
						root = obj.root
						break
			
				if root is None:
					# Fallback - create temporary root
					root = tk.Tk()
					root.withdraw()
			
				# Create calibration popup
				popup = tk.Toplevel(root)
				popup.title("Calibrating")
				popup.geometry("350x140")
				popup.configure(bg='#2F4F4F')
				popup.transient(root)
				popup.grab_set()
				popup.resizable(False, False)
			
				# Center the popup
				popup.update_idletasks()
				x = (popup.winfo_screenwidth() // 2) - (350 // 2)
				y = (popup.winfo_screenheight() // 2) - (140 // 2)
				popup.geometry(f"350x140+{x}+{y}")
			
				# Popup content
				tk.Label(
					popup,
					text="Calibrating...",
					font=('Arial', 16, 'bold'),
					bg='#2F4F4F',
					fg='#ffffff'
				).pack(pady=15)
				
				tk.Label(
					popup,
					text="Measuring audio system latency.",
					font=('Arial', 11),
					bg='#2F4F4F',
					fg='#ffffff'
				).pack()
			
				tk.Label(
					popup,
					text="Please wait a moment...",
					font=('Arial', 11),
					bg='#2F4F4F',
					fg='#ffffff'
				).pack()
			
				# Progress bar
				progress = ttk.Progressbar(
					popup, 
					mode='indeterminate',
					length=200
				)
				progress.pack(pady=15)
				progress.start()
			
				popup.update()
				return popup, progress
			
			except Exception as e:
				print(f"Could not create calibration popup: {e}")
				return None, None
	
		def calibration_thread():
			popup = None
			progress = None
		
			try:
				print("Starting latency calibration...")
			
				# Show popup in main thread
				try:
					# Try to get UI controller reference
					import threading
					main_thread = threading.main_thread()
					if hasattr(main_thread, 'ui_controller'):
						ui = main_thread.ui_controller
						popup, progress = ui.root.after(0, show_calibration_popup)
				except:
					pass
			
				# Run latency measurement
				self.measure_latency()
			
				# Close popup if it was created
				if popup:
					popup.after(0, lambda: popup.destroy())
				
			except Exception as e:
				print(f"Startup calibration failed: {e}")
				# Fallback to conservative estimate
				self.measured_latency_samples = self.buffer_size * 3
				self.measured_latency_ms = (self.measured_latency_samples / self.sample_rate) * 1000
				print(f"Using estimated latency: {self.measured_latency_ms:.1f}ms")
			
				if popup:
					popup.after(0, lambda: popup.destroy())
	
		# Run calibration in background thread
		threading.Thread(target=calibration_thread, daemon=True).start()
		
	def measure_latency(self):
		"""Measure system latency by taking multiple measurements and averaging"""
		try:
			print("Measuring system latency with 10 samples...")
			latency_measurements = []
			
			for measurement_num in range(4):
				print(f"Taking measurement {measurement_num + 1}/4...")
				
				# Generate a test click
				click_duration = 0.05  # 50ms click
				click_samples = int(self.sample_rate * click_duration)
				test_click = np.sin(2 * np.pi * 1000 * np.linspace(0, click_duration, click_samples)) * 0.5
				
				# Recording variables
				recorded_data = []
				click_played = False
				
				def latency_callback(indata, outdata, frames, time_info, status):
					nonlocal click_played
					recorded_data.extend(indata.flatten())
					
					# Play the click once at the beginning
					if not click_played and len(recorded_data) < frames * 2:
						click_start = 0
						click_end = min(frames, len(test_click))
						outdata[:click_end, 0] = test_click[click_start:click_end]
						outdata[:click_end, 1] = test_click[click_start:click_end]
						outdata[click_end:, :] = 0
						click_played = True
					else:
						outdata.fill(0)
				
				# Record for analysis
				test_duration = 0.5  # 500ms should be enough
				with sd.Stream(
					samplerate=self.sample_rate,
					device=(self.input_device, self.output_device),
					channels=(1, 2),
					callback=latency_callback,
					blocksize=self.buffer_size,
					latency='low'
				):
					sd.sleep(int(test_duration * 1000))
				
				# Analyze recorded data
				if len(recorded_data) < click_samples:
					print(f"Measurement {measurement_num + 1} failed: insufficient data")
					continue
					
				recorded_array = np.array(recorded_data)
				
				# Find the click in recorded data using cross-correlation
				correlation = np.correlate(recorded_array, test_click, mode='full')
				peak_index = np.argmax(correlation)
				
				# Calculate latency - account for correlation offset
				expected_position = len(test_click) - 1
				actual_position = peak_index
				latency_samples = actual_position - expected_position

				
				# Validate this measurement
				latency_ms = (latency_samples / self.sample_rate) * 1000
				latency_measurements.append(latency_samples)
				print(f"Measurement {measurement_num + 1}: {latency_ms:.1f}ms")
				
				# Short delay between measurements
				time.sleep(0.1)
			
			# Calculate average latency
			if len(latency_measurements) >= 2:  # Need at least 2 valid measurements
				# Remove outliers (highest and lowest values)
				if len(latency_measurements) >= 4:
					latency_measurements.sort()
					latency_measurements = latency_measurements[1:-1]  # Remove highest and lowest
	
				average_latency_samples = sum(latency_measurements) // len(latency_measurements)
				std_deviation = np.std(latency_measurements)
	
				self.measured_latency_samples = average_latency_samples
				self.measured_latency_ms = (average_latency_samples / self.sample_rate) * 1000
				self.latency_calibrated = True
	
				print(f"✓ Average latency from {len(latency_measurements)} measurements:")
				print(f"  {self.measured_latency_ms:.1f}ms ± {(std_deviation/self.sample_rate)*1000:.1f}ms")
				print(f"  ({self.measured_latency_samples} samples)")
				return average_latency_samples
	
			else:
				raise Exception(f"Only {len(latency_measurements)} valid measurements - need at least 2")
				
		except Exception as e:
			print(f"Latency measurement failed: {e}")
			# Conservative fallback estimate
			self.measured_latency_samples = self.buffer_size * 4
			self.measured_latency_ms = (self.measured_latency_samples / self.sample_rate) * 1000
			print(f"Using conservative estimate: {self.measured_latency_ms:.1f}ms")
			return self.measured_latency_samples
			
	def initialize_devices(self):
		"""Initialize and catalog available audio devices with Sound Mapper defaults"""
		try:
			devices = sd.query_devices()
			self.available_input_devices = []
			self.available_output_devices = []
			
			input_devices = []
			output_devices = []
			
			# Look for Microsoft Sound Mapper first
			sound_mapper_input = None
			sound_mapper_output = None
			
			for i, device in enumerate(devices):
				device_name = device['name'].lower()
				
				# Identify Sound Mapper devices
				if 'microsoft sound mapper' in device_name:
					if device['max_input_channels'] > 0:
						sound_mapper_input = i
					if device['max_output_channels'] > 0:
						sound_mapper_output = i
				
				# Catalog all devices
				if device['max_input_channels'] > 0:
					input_devices.append({
						'index': i,
						'name': device['name'],
						'channels': device['max_input_channels']
					})
				
				if device['max_output_channels'] > 0:
					output_devices.append({
						'index': i,
						'name': device['name'],
						'channels': device['max_output_channels']
					})
			
			# Set Sound Mapper as defaults if available, otherwise fall back
			self.input_device = sound_mapper_input if sound_mapper_input is not None else sd.default.device[0]
			self.output_device = sound_mapper_output if sound_mapper_output is not None else sd.default.device[1]
			
			# Sort and deduplicate device lists
			seen_input_names = set()
			for device in sorted(input_devices, key=lambda x: (0 if 'microsoft sound mapper' in x['name'].lower() else 1, x['name'])):
				if device['name'] not in seen_input_names:
					self.available_input_devices.append(device)
					seen_input_names.add(device['name'])

			seen_output_names = set()
			for device in sorted(output_devices, key=lambda x: (0 if 'microsoft sound mapper' in x['name'].lower() else 1, x['name'])):
				if device['name'] not in seen_output_names:
					self.available_output_devices.append(device)
					seen_output_names.add(device['name'])			

			print(f"Default input: {sd.query_devices(self.input_device)['name']}")
			print(f"Default output: {sd.query_devices(self.output_device)['name']}")
		
		except Exception as e:
			print(f"Error initializing devices: {e}")
			
	def get_input_devices(self):
		"""Get list of available input devices"""
		return self.available_input_devices
		
	def get_output_devices(self):
		"""Get list of available output devices"""
		return self.available_output_devices
		
	def set_input_device(self, device_index):
		"""Set input device by index"""
		try:
			device = sd.query_devices(device_index)
			if device['max_input_channels'] > 0:
				self.input_device = device_index
				print(f"Input device set to: {device['name']}")
				return True
		except:
			pass
		return False
		
	def set_output_device(self, device_index):
		"""Set output device by index"""
		try:
			device = sd.query_devices(device_index)
			if device['max_output_channels'] > 0:
				self.output_device = device_index
				print(f"Output device set to: {device['name']}")
				return True
		except:
			pass
		return False
			
	def initialize_metronome(self):	
		"""Create metronome click sounds - try to load cowbell.mp3 and and1.mp3"""
		# Initialize to None first
		self.metronome_sound = None
		self.metronome_and_sound = None
		
		# Function to get the correct path for bundled files
		def get_resource_path(relative_path):
			"""Get absolute path to resource, works for dev and for PyInstaller"""
			try:
				# PyInstaller creates a temp folder and stores path in _MEIPASS
				import sys
				base_path = sys._MEIPASS
			except AttributeError:
				base_path = os.path.abspath(".")
			return os.path.join(base_path, relative_path)
	
		# Load main metronome sound (cowbell.mp3 or generated)
		try:
			# Try to load cowbell.mp3 from root folder
			cowbell_file = get_resource_path("cowbell.mp3")
			if os.path.exists(cowbell_file):  # Use os.path.exists() instead of .exists()
				print("Loading cowbell.mp3...")
				audio_data, sample_rate = sf.read(cowbell_file)  # No need for str() conversion
				
				# Resample if needed
				if sample_rate != self.sample_rate:
					try:
						from scipy import signal
						num_samples = int(len(audio_data) * self.sample_rate / sample_rate)
						audio_data = signal.resample(audio_data, num_samples)
					except ImportError:
						# Fallback: simple linear interpolation
						ratio = self.sample_rate / sample_rate
						new_length = int(len(audio_data) * ratio)
						audio_data = np.interp(
							np.linspace(0, len(audio_data)-1, new_length),
							np.arange(len(audio_data)),
							audio_data
						)
				
				# Convert to mono if stereo
				if len(audio_data.shape) > 1:
					audio_data = np.mean(audio_data, axis=1)
				
				# Normalize and limit duration to 200ms max
				max_samples = int(0.2 * self.sample_rate)
				if len(audio_data) > max_samples:
					audio_data = audio_data[:max_samples]
					
				# Apply fade out to avoid clicks
				fade_samples = int(0.01 * self.sample_rate)  # 10ms fade
				if len(audio_data) > fade_samples:
					fade_curve = np.linspace(1, 0, fade_samples)
					audio_data[-fade_samples:] *= fade_curve
				
				self.metronome_sound = audio_data.astype(self.dtype)
				print("✓ Loaded cowbell.mp3 for metronome")
			else:
				raise Exception("cowbell.mp3 not found")
					
		except Exception as e:
			print(f"Could not load cowbell.mp3: {e}, creating generated sound")
			# Fallback to generated click sound
			duration = 0.05  # 50ms
			samples = int(self.sample_rate * duration)
			t = np.linspace(0, duration, samples)
			frequency = 1000  # Hz
			
			# Create click with envelope to avoid pops
			click = np.sin(2 * np.pi * frequency * t) * 0.5
			envelope = np.exp(-t * 20)  # Exponential decay
			self.metronome_sound = (click * envelope).astype(self.dtype)
			print("✓ Using generated click for metronome")
		
		# Load "and" sound for every 4th beat (and1.mp3)
		try:
			and1_file = get_resource_path("and1.mp3")
			if os.path.exists(and1_file):  # Use os.path.exists() instead of .exists()
				print("Loading and1.mp3...")
				audio_data, sample_rate = sf.read(and1_file)  # No need for str() conversion
				
				# Resample if needed
				if sample_rate != self.sample_rate:
					try:
						from scipy import signal
						num_samples = int(len(audio_data) * self.sample_rate / sample_rate)
						audio_data = signal.resample(audio_data, num_samples)
					except ImportError:
						# Fallback: simple linear interpolation
						ratio = self.sample_rate / sample_rate
						new_length = int(len(audio_data) * ratio)
						audio_data = np.interp(
							np.linspace(0, len(audio_data)-1, new_length),
							np.arange(len(audio_data)),
							audio_data
						)
				
				# Convert to mono if stereo
				if len(audio_data.shape) > 1:
					audio_data = np.mean(audio_data, axis=1)
				
				# Normalize and limit duration to 200ms max
				max_samples = int(0.2 * self.sample_rate)
				if len(audio_data) > max_samples:
					audio_data = audio_data[:max_samples]
					
				# Apply fade out to avoid clicks
				fade_samples = int(0.01 * self.sample_rate)  # 10ms fade
				if len(audio_data) > fade_samples:
					fade_curve = np.linspace(1, 0, fade_samples)
					audio_data[-fade_samples:] *= fade_curve
				
				self.metronome_and_sound = audio_data.astype(self.dtype)
				print("✓ Loaded and1.mp3 for metronome 'and' beats")
			else:
				# Use the same sound for "and" beats if and1.mp3 not found
				self.metronome_and_sound = self.metronome_sound.copy()
				print("✓ Using same sound for 'and' beats (and1.mp3 not found)")
				
		except Exception as e:
			print(f"Could not load and1.mp3: {e}")
			# Use the same sound for "and" beats
			if self.metronome_sound is not None:
				self.metronome_and_sound = self.metronome_sound.copy()
				print("✓ Using main metronome sound for 'and' beats")
			
	def calculate_metronome_timing(self):
		"""Calculate samples per beat based on BPM"""
		if self.bpm > 0:
			beats_per_second = self.bpm / 60.0
			self.samples_per_beat = int(self.sample_rate / beats_per_second)
		else:
			self.samples_per_beat = self.sample_rate  # Default to 1 second if BPM is 0
		
	def set_bpm(self, bpm):
		"""Set metronome BPM"""
		self.bpm = max(60, min(200, bpm))  # Clamp between 60-200
		self.calculate_metronome_timing()
		
	def set_metronome_volume(self, volume):
		"""Set metronome volume (0.0 to 1.0) with 12 dB boost at 100%"""
		self.metronome_volume = max(0.0, min(1.0, volume))
		
	def get_effective_metronome_volume(self):
		"""Get effective metronome volume with 12 dB boost (4x gain) at 100%"""
		if self.metronome_volume == 0:
			return 0
		# Apply 12 dB (4x) gain boost: volume scales from 0-1 to 0-4
		return self.metronome_volume * 4.0
		
	def audio_callback(self, indata, outdata, frames, time_info, status):
		"""UPDATED real-time audio callback with volume and FX processing"""
		if status:
			print(f"Audio callback status: {status}")
			
		# Initialize output - use fill for better performance
		outdata.fill(0)
		
		# Handle recording with minimal processing
		if self.is_recording and self.recording_track is not None:
			with self.recording_lock:
				# Convert input to mono if needed - optimized
				mono_input = indata[:, 0] if indata.shape[1] > 1 else indata.flatten()
				self.recording_buffer.extend(mono_input)
				
				# Quick level calculation for recording track - apply volume for level display
				input_level = np.max(np.abs(mono_input))
				self.track_levels[self.recording_track] = max(
					self.track_levels[self.recording_track] * 1,
					input_level
				)
				self.update_track_level(self.recording_track, input_level)

		elif not self.is_recording:
			armed_track = None
			if self.track_manager:
				try:
					armed_track = self.track_manager.get_armed_track()
				except:
					armed_track = None

			if armed_track is not None:
				# Monitor input level for armed track
				mono_input = indata[:, 0] if indata.shape[1] > 1 else indata.flatten()
				input_level = np.max(np.abs(mono_input))
				self.track_levels[armed_track] = max(
					self.track_levels[armed_track] * 1,
					input_level
				)
				self.update_track_level(armed_track, input_level)

		# Apply decay to all track levels efficiently
		for track_num in self.track_levels:
			self.track_levels[track_num] *= self.level_decay
		
		# Handle playback - streamlined with volume and FX
		if self.is_playing:
			with self.playback_lock:
				# Pre-allocate output buffer
				mixed_output = np.zeros((frames, 2), dtype=self.dtype)
				
				# Get playable tracks (considering mute/solo)
				playable_tracks = self.get_playable_tracks()
				
				# Mix tracks efficiently with volume and FX
				for track_num in playable_tracks:
					if track_num in self.track_data:
						track_len = self.track_lengths[track_num]
						
						if self.playback_position < track_len:
							remaining_samples = track_len - self.playback_position
							samples_to_read = min(frames, remaining_samples)
							
							# Get track data segment
							track_segment = self.track_data[track_num][
								self.playback_position:self.playback_position + samples_to_read
							]
							
							if len(track_segment) > 0:
								# Apply volume
								track_volume = self.track_volumes.get(track_num, 0.75)
								processed_segment = track_segment * track_volume
								
								# Apply FX processing
								processed_segment = self.process_track_fx(track_num, processed_segment)
								
								# Update level for visual feedback (after processing)
								track_level = np.max(np.abs(processed_segment))
								self.track_levels[track_num] = max(
									self.track_levels[track_num],
									track_level
								)
								self.update_track_level(track_num, track_level)
								
								# Convert mono to stereo and mix - optimized
								segment_len = len(processed_segment)
								mixed_output[:segment_len, 0] += processed_segment
								mixed_output[:segment_len, 1] += processed_segment
				
				# Add metronome if enabled
				if self.metronome_enabled:
					self.add_metronome_optimized(mixed_output, frames)
				
				# Apply master volume and copy to output buffer
				if self.master_volume_gain != 1.0:
					mixed_output *= self.master_volume_gain
				outdata[:] = mixed_output
				
				# Advance playback position
				self.playback_position += frames
	
	def get_playable_tracks(self):
		"""Get list of tracks that should be played (considering mute/solo)"""
		if not self.track_manager:
			# Fallback if track manager not set
			return list(self.track_data.keys())
		
		# Use track manager's logic for playable tracks
		return self.track_manager.get_playable_tracks()
		
	def add_metronome_optimized(self, output, frames):
		"""Optimized metronome addition with 'and' sound every 4th beat"""
		effective_volume = self.get_effective_metronome_volume()
		
		if effective_volume == 0 or self.samples_per_beat == 0:
			return
		
		for i in range(frames):
			beat_position = (self.playback_position + i) % self.samples_per_beat
			
			# Trigger click at beat start - use a wider window but prevent multiple triggers
			if beat_position < len(self.metronome_sound):
				# Determine which beat we're on (1, 2, 3, 4, 1, 2, 3, 4...)
				current_sample = self.playback_position + i
				current_beat = (current_sample // self.samples_per_beat) % 4 + 1
				
				# Use "and" sound for beat 1 (every 4th beat starting with first)
				if current_beat == 1 and hasattr(self, 'metronome_and_sound'):
					sound_to_use = self.metronome_and_sound
				else:
					sound_to_use = self.metronome_sound
				
				# Play the appropriate sound
				if beat_position < len(sound_to_use):
					click_sample = sound_to_use[beat_position] * effective_volume
					output[i, 0] += click_sample  # Left channel
					output[i, 1] += click_sample  # Right channel
		
	def update_track_level(self, track_num, new_level):
		"""Update track level with peak detection"""
		current_time = time.time()
		
		# Initialize if needed
		if track_num not in self.track_levels:
			self.track_levels[track_num] = 0.0
			self.track_peaks[track_num] = False
			self.peak_hold_time[track_num] = 0.0
		
		# Update level (use max of current and new for better visualization)
		self.track_levels[track_num] = max(self.track_levels[track_num], new_level)
		
		# Peak detection - use 0.95 instead of 0.7 for full range usage
		if new_level >= 1:
			self.track_peaks[track_num] = True
			self.peak_hold_time[track_num] = current_time
		elif current_time - self.peak_hold_time[track_num] > self.peak_hold_duration:
			self.track_peaks[track_num] = False
			
	def get_track_level(self, track_num):
		"""Get current level for track (0.0 to 1.0)"""
		level = self.track_levels.get(track_num, 0.0)
		# Apply some minimum threshold to avoid tiny values
		return level if level > 0.001 else 0.0
		
	def get_track_peak(self, track_num):
		"""Get peak status for track"""
		return self.track_peaks.get(track_num, False)
		
	def export_mixdown_mp3(self, project_name):
		"""Export all tracks as a single MP3 file"""
		try:
			# Create export directory
			export_dir = Path("exported_mp3s")
			export_dir.mkdir(exist_ok=True)
			
			# Find the longest track to determine mix length
			max_length = 0
			playable_tracks = []
			
			for track_num in range(1, 9):
				if self.has_track_data(track_num):
					# Check if track should be included (not muted)
					track = self.track_manager.get_track(track_num) if self.track_manager else None
					if not track or not track.is_muted:
						playable_tracks.append(track_num)
						track_length = self.track_lengths.get(track_num, 0)
						max_length = max(max_length, track_length)
			
			if max_length == 0:
				print("No audio data to export")
				return False
			
			print(f"Mixing {len(playable_tracks)} tracks, total length: {max_length/self.sample_rate:.2f} seconds")
			
			# Create stereo mix buffer
			mixdown = np.zeros((max_length, 2), dtype=self.dtype)
			
			# Mix all playable tracks
			for track_num in playable_tracks:
				if track_num in self.track_data:
					track_data = self.track_data[track_num]
					track_length = len(track_data)
					
					# Apply volume
					track_volume = self.track_volumes.get(track_num, 0.75)
					processed_track = track_data * track_volume
					
					# Apply FX processing  
					processed_track = self.process_track_fx(track_num, processed_track)
					
					# Add to stereo mixdown
					mixdown[:track_length, 0] += processed_track  # Left channel
					mixdown[:track_length, 1] += processed_track  # Right channel
					
					print(f"Mixed track {track_num} (volume: {track_volume:.2f}, fx: {self.track_fx.get(track_num, 'none')})")
			
			# Normalize mixdown to prevent clipping
			max_level = np.max(np.abs(mixdown))
			if max_level > 0.95:
				normalization_factor = 0.95 / max_level
				mixdown *= normalization_factor
				print(f"Normalized mixdown by {normalization_factor:.3f} to prevent clipping")
			
			# Save as WAV first
			safe_project_name = self.make_safe_filename(project_name)
			wav_filename = export_dir / f"{safe_project_name}_mixdown.wav"
			sf.write(str(wav_filename), mixdown, self.sample_rate)
			print(f"Saved WAV mixdown: {wav_filename}")
			
			# Convert to MP3
			try:
				# Try importing pydub for MP3 conversion
				from pydub import AudioSegment
				
				# Load WAV and export as MP3
				audio = AudioSegment.from_wav(str(wav_filename))
				mp3_filename = export_dir / f"{safe_project_name}_mixdown.mp3"
				audio.export(str(mp3_filename), format="mp3", bitrate="192k")
				
				# Delete temporary WAV file
				wav_filename.unlink()
				
				print(f"✓ Exported MP3 mixdown: {mp3_filename}")
				return True
				
			except ImportError:
				print("Warning: pydub not available for MP3 conversion")
				print(f"✓ Exported WAV mixdown: {wav_filename}")
				print("Install pydub for MP3 support: pip install pydub")
				return True
				
		except Exception as e:
			print(f"Error exporting mixdown: {e}")
			return False
			
	def start_stream(self):
		"""Start audio stream with low-latency settings"""
		if self.stream is not None:
			self.stop_stream()
			
		try:
			input_dev = self.input_device if self.input_device is not None else sd.default.device[0]
			output_dev = self.output_device if self.output_device is not None else sd.default.device[1]
			
			# Try ASIO first on Windows for lower latency
			extra_settings = None
			if os.name == 'nt':  # Windows
				try:
					# Look for ASIO devices
					devices = sd.query_devices()
					for device in devices:
						if 'asio' in device['name'].lower():
							print(f"Found ASIO device: {device['name']}")
							break
				except:
					pass
			
			self.stream = sd.Stream(
				samplerate=self.sample_rate,
				device=(input_dev, output_dev),
				channels=(1, 2),  # Mono input, stereo output
				dtype=self.dtype,
				callback=self.audio_callback,
				blocksize=self.buffer_size,
				latency='low',  # Request low latency
				extra_settings=extra_settings,
				prime_output_buffers_using_stream_callback=True
			)
			self.stream.start()
			print(f"✓ Audio stream started with {self.buffer_size} sample buffer")
			return True
		except Exception as e:
			print(f"Failed to start audio stream: {e}")
			return False
			
	def stop_stream(self):
		"""Stop audio stream"""
		if self.stream is not None:
			self.stream.stop()
			self.stream.close()
			self.stream = None
			
	def start_recording(self, track_number):
		"""Start recording to specified track"""
		if not self.stream or not self.stream.active:
			if not self.start_stream():
				return False
				
		with self.recording_lock:
			self.is_recording = True
			self.recording_track = track_number
			self.recording_buffer = []
			
		print(f"Started recording to track {track_number}")
		return True
		
	def stop_recording(self):
		"""Stop recording and save to file WITH LATENCY COMPENSATION"""
		if not self.is_recording:
			return None
			
		with self.recording_lock:
			self.is_recording = False
			track_num = self.recording_track
			buffer_copy = self.recording_buffer.copy()
			self.recording_buffer = []
			self.recording_track = None
		
		if len(buffer_copy) > 0 and track_num is not None:
			# Convert to numpy array
			audio_data = np.array(buffer_copy, dtype=self.dtype)
			
			# Apply latency compensation - trim the beginning
			if self.measured_latency_samples > 0:
				if len(audio_data) > self.measured_latency_samples:
					audio_data = audio_data[self.measured_latency_samples:]
					print(f"✓ Applied latency compensation: removed {self.measured_latency_ms:.1f}ms")
				else:
					print("⚠ Recording too short for latency compensation")
			
			# Store in track data
			self.track_data[track_num] = audio_data
			self.track_lengths[track_num] = len(audio_data)
			
			# Save to project-specific directory
			recordings_dir = Path(self.recordings_dir)
			recordings_dir.mkdir(parents=True, exist_ok=True)
			filename = recordings_dir / f"track_{track_num}_{int(time.time())}.wav"
			
			try:
				sf.write(str(filename), audio_data, self.sample_rate)
				print(f"Saved recording: {filename}")
				return str(filename)
			except Exception as e:
				print(f"Failed to save recording: {e}")
				
		return None
		
	def start_playback(self):
		"""Start playback of all tracks"""
		if not self.stream or not self.stream.active:
			if not self.start_stream():
				return False
				
		with self.playback_lock:
			self.is_playing = True
			self.playback_position = 0
			self.playback_start_time = time.time()
			
		print("Started playback")
		return True
		
	def pause_playback(self):
		"""Pause playback"""
		with self.playback_lock:
			self.is_playing = False
		print("Paused playback")
		
	def stop_playback(self):
		"""Stop playback and reset position"""
		with self.playback_lock:
			self.is_playing = False
			self.playback_position = 0
			self.playback_start_time = 0
		print("Stopped playback")
		
	def get_playback_time(self):
		"""Get current playback time in seconds"""
		if self.is_playing:
			return self.playback_position / self.sample_rate
		return 0
		
	def format_time(self, seconds):
		"""Format time as MM:SS"""
		minutes = int(seconds // 60)
		seconds = int(seconds % 60)
		return f"{minutes:02d}:{seconds:02d}"
		
	def clear_track(self, track_number):
		"""Clear specific track"""
		if track_number in self.track_data:
			del self.track_data[track_number]
		if track_number in self.track_lengths:
			del self.track_lengths[track_number]
		# Clear level data for the track
		if track_number in self.track_levels:
			self.track_levels[track_number] = 0.0
		if track_number in self.track_peaks:
			self.track_peaks[track_number] = False
		print(f"Cleared track {track_number}")
		
	def set_metronome(self, enabled):
		"""Enable/disable metronome"""
		self.metronome_enabled = enabled
		print(f"Metronome {'enabled' if enabled else 'disabled'}")
		
	def get_track_count(self):
		"""Get number of recorded tracks"""
		return len(self.track_data)
		
	def has_track_data(self, track_number):
		"""Check if track has recorded data"""
		return track_number in self.track_data and len(self.track_data[track_number]) > 0
		
	def set_recordings_directory(self, recordings_dir):
		"""Set the recordings directory for current project"""
		self.recordings_dir = Path(recordings_dir)
		self.recordings_dir.mkdir(parents=True, exist_ok=True)
		print(f"Recordings directory set to: {self.recordings_dir}")
		
	def get_latency_info(self):
		"""Get latency compensation info for UI display"""
		return {
			'measured_ms': self.measured_latency_ms,
			'measured_samples': self.measured_latency_samples,
			'calibrated': self.latency_calibrated,
			'buffer_size': self.buffer_size
		}
		
	def load_project_audio_files(self, project_name):
		"""Load audio files for a specific project"""
		try:
			# Clear current audio data first
			self.track_data.clear()
			self.track_lengths.clear()
		
			# Reset all track levels
			for i in range(1, 9):
				self.track_levels[i] = 0.0
				self.track_peaks[i] = False
				self.peak_hold_time[i] = 0.0
		
			# Look for audio files in the project's recordings directory
			safe_project_name = self.make_safe_filename(project_name)
			project_recordings_dir = Path("recordings") / safe_project_name
		
			if not project_recordings_dir.exists():
				# Try old format without safe filename
				project_recordings_dir = Path("recordings") / project_name
				if not project_recordings_dir.exists():
					print(f"No recordings directory found for project: {project_name}")
					return
			
			# Load the most recent audio file for each track
			loaded_count = 0
			for track_num in range(1, 9):
				# Try multiple patterns
				patterns = [
					f"track_{track_num}_*.wav",
					f"{safe_project_name}_track_{track_num}_*.wav"
				]
			
				track_files = []
				for pattern in patterns:
					track_files.extend(list(project_recordings_dir.glob(pattern)))
			
				if track_files:
					# Get the most recent file for this track
					latest_file = max(track_files, key=lambda p: p.stat().st_mtime)
				
					try:
						# Load the audio file
						audio_data, sample_rate = sf.read(str(latest_file))
					
						# Resample if needed
						if sample_rate != self.sample_rate:
							print(f"Resampling track {track_num} from {sample_rate}Hz to {self.sample_rate}Hz")
							try:
								from scipy import signal
								num_samples = int(len(audio_data) * self.sample_rate / sample_rate)
								audio_data = signal.resample(audio_data, num_samples)
							except ImportError:
								# Fallback resampling
								ratio = self.sample_rate / sample_rate
								new_length = int(len(audio_data) * ratio)
								audio_data = np.interp(
									np.linspace(0, len(audio_data)-1, new_length),
									np.arange(len(audio_data)),
									audio_data
								)
					
						# Convert to mono if stereo
						if len(audio_data.shape) > 1:
							audio_data = np.mean(audio_data, axis=1)
					
						# Store in track data
						self.track_data[track_num] = audio_data.astype(self.dtype)
						self.track_lengths[track_num] = len(audio_data)
						loaded_count += 1
					
						print(f"✓ Loaded audio for track {track_num}: {latest_file.name}")
					
					except Exception as e:
						print(f"✗ Failed to load audio for track {track_num}: {e}")
		
			print(f"Loaded {loaded_count} audio files for project: {project_name}")
		
		except Exception as e:
			print(f"Error loading project audio files: {e}")
			
	def make_safe_filename(self, filename):
		"""Convert filename to safe format"""
		# Remove or replace invalid characters
		invalid_chars = '<>:"/\\|?*'
		safe_name = filename
		
		for char in invalid_chars:
			safe_name = safe_name.replace(char, '_')
			
		# Remove leading/trailing spaces and dots
		safe_name = safe_name.strip(' .')
		
		# Ensure not empty
		if not safe_name:
			safe_name = "untitled"
			
		return safe_name
		
	def clear_all_project_data(self):
		"""Clear all project audio data - for NEW PROJECT"""
		try:
			# Clear all track data
			self.track_data.clear()
			self.track_lengths.clear()
			
			# Reset all track levels and peaks
			for i in range(1, 9):
				self.track_levels[i] = 0.0
				self.track_peaks[i] = False
				self.peak_hold_time[i] = 0.0
				# Reset track settings to defaults
				self.track_volumes[i] = 0.75
				self.track_fx[i] = "none"
				self.fx_processors[i] = {}
			
			# Stop any ongoing playback/recording
			self.stop_playback()
			if self.is_recording:
				self.is_recording = False
				with self.recording_lock:
					self.recording_buffer.clear()
					self.recording_track = None
			
			print("✓ Cleared all project audio data")
			
		except Exception as e:
			print(f"Error clearing project data: {e}")
		
	def cleanup(self):
		"""Clean up audio resources"""
		self.stop_stream()
		print("Audio engine cleaned up")