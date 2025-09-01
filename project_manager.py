"""
Project Manager - Handles saving and loading of multitrack projects
UPDATED to save volume and FX settings
"""

import json
import os
from pathlib import Path
from datetime import datetime
import shutil
import glob

class ProjectManager:
	def __init__(self):
		self.current_project = None
		self.current_project_name = "Default Project"
		self.projects_dir = Path("projects")
		self.recordings_dir = Path("recordings") 
		self.default_project_name = "Untitled Project"
		
		# Ensure directories exist
		self.projects_dir.mkdir(exist_ok=True)
		self.recordings_dir.mkdir(exist_ok=True)
		
	def set_project_name(self, name):
		"""Set current project name and create folder structure"""
		if not name or name.strip() == "":
			name = "Default Project"
			
		self.current_project_name = name.strip()
		
		# Create project-specific recordings directory only
		recordings_folder = self.recordings_dir / self.make_safe_filename(self.current_project_name)
		recordings_folder.mkdir(exist_ok=True)
		
		print(f"Project set to: {self.current_project_name}")
		print(f"Recordings will be saved to: {recordings_folder}")
		
		return str(recordings_folder)
		
	def get_current_recordings_folder(self):
		"""Get the recordings folder for current project"""
		recordings_folder = self.recordings_dir / self.make_safe_filename(self.current_project_name)
		recordings_folder.mkdir(exist_ok=True)
		return str(recordings_folder)
		
	def create_new_project(self, name=None):
		"""Create a new empty project"""
		if name is None:
			timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
			name = f"Project_{timestamp}"
			
		self.current_project = {
			'name': name,
			'created': datetime.now().isoformat(),
			'modified': datetime.now().isoformat(),
			'bpm': 120,
			'metronome_enabled': False,
			'tracks': {}
		}
		
		print(f"Created new project: {name}")
		return True
		
	def save_project(self, track_manager, audio_engine, name=None):
		"""Save current project state directly to projects folder"""
		if self.current_project is None:
			self.create_new_project(name)
		elif name:
			self.current_project['name'] = name
			
		# Update project data
		self.current_project['modified'] = datetime.now().isoformat()
		self.current_project['bpm'] = audio_engine.bpm
		self.current_project['metronome_enabled'] = audio_engine.metronome_enabled
		
		# Save track states including volume and FX
		self.current_project['tracks'] = {}
		for track_num in range(1, 9):
			track = track_manager.get_track(track_num)		
			if track:
				# Check audio engine for actual data presence
				actual_has_data = audio_engine.has_track_data(track_num)
				self.current_project['tracks'][track_num] = {
					'has_data': actual_has_data,  # Use actual data presence
					'is_muted': track.is_muted,
					'volume': track.volume,
					'name': track.name,
					# Save FX settings from audio engine
					'fx_type': audio_engine.get_track_fx(track_num),
					'track_volume': audio_engine.get_track_volume(track_num)
				}
		
		# Save project file directly to projects folder (no subfolders)
		project_name = self.current_project['name']
		safe_name = self.make_safe_filename(project_name)
		project_file = self.projects_dir / f"{safe_name}.json"
		
		try:
			with open(project_file, 'w') as f:
				json.dump(self.current_project, f, indent=2)
			print(f"Project saved: {project_file}")
			return str(project_file)
		except Exception as e:
			print(f"Error saving project: {e}")
			return None
			
	def load_project(self, project_file):
		"""Load project from file"""
		try:
			with open(project_file, 'r') as f:
				self.current_project = json.load(f)
			print(f"Project loaded: {project_file}")
			return True
		except Exception as e:
			print(f"Error loading project: {e}")
			return False
			
	def apply_project_to_managers(self, track_manager, audio_engine):
		"""Apply loaded project settings to managers"""
		if self.current_project is None:
			return False
		
		try:
			# Apply audio engine settings
			audio_engine.set_bpm(self.current_project.get('bpm', 120))
			audio_engine.set_metronome(self.current_project.get('metronome_enabled', False))
			# REMOVED: audio_engine.set_current_project_name - this method doesn't exist
		
			# Apply track settings
			tracks_data = self.current_project.get('tracks', {})
			for track_num_str, track_data in tracks_data.items():
				track_num = int(track_num_str)
				track = track_manager.get_track(track_num)
			
				if track:
					# Don't set has_data here - it will be set after audio files are loaded
					track.is_muted = track_data.get('is_muted', False)
					track.set_volume(track_data.get('volume', 1.0))
					track.name = track_data.get('name', f"Track {track_num}")
				
					# Apply FX settings to audio engine
					fx_type = track_data.get('fx_type', 'none')
					audio_engine.set_track_fx(track_num, fx_type)
				
					# Apply volume settings to audio engine
					track_volume = track_data.get('track_volume', 0.75)
					audio_engine.set_track_volume(track_num, track_volume)
				
			print("Project settings applied to managers")
			return True
		except Exception as e:
			print(f"Error applying project settings: {e}")
			return False
			
	def get_project_list(self):
		"""Get list of available projects"""
		projects = []
		
		try:
			for project_file in self.projects_dir.glob("*.json"):
				try:
					with open(project_file, 'r') as f:
						project_data = json.load(f)
					
					projects.append({
						'name': project_data.get('name', project_file.stem),
						'file': str(project_file),
						'created': project_data.get('created', ''),
						'modified': project_data.get('modified', ''),
						'track_count': len([t for t in project_data.get('tracks', {}).values() 
										  if t.get('has_data', False)])
					})
				except:
					# Skip corrupted project files
					continue
					
		except Exception as e:
			print(f"Error getting project list: {e}")
			
		# Sort by modified date (newest first)
		projects.sort(key=lambda x: x['modified'], reverse=True)
		return projects
		
	def delete_project(self, project_file):
		"""Delete a project file"""
		try:
			Path(project_file).unlink()
			print(f"Deleted project: {project_file}")
			return True
		except Exception as e:
			print(f"Error deleting project: {e}")
			return False
			
	def delete_track_files(self, track_num):
		"""Delete all recording files associated with a specific track"""
		try:
			deleted_count = 0
			
			# Get current project's recording directory
			recordings_folder = Path(self.get_current_recordings_folder())
			
			# Create pattern for current project's track files
			safe_project_name = self.make_safe_filename(self.current_project_name)
			patterns = [
				f"{safe_project_name}_track_{track_num}_*.wav",  # New naming format
				f"track_{track_num}_*.wav"  # Legacy naming format
			]
			
			for pattern in patterns:
				for audio_file in recordings_folder.glob(pattern):
					try:
						audio_file.unlink()
						deleted_count += 1
						print(f"Deleted: {audio_file}")
					except Exception as e:
						print(f"Failed to delete {audio_file}: {e}")
			
			print(f"Deleted {deleted_count} files for track {track_num}")
			return deleted_count
			
		except Exception as e:
			print(f"Error deleting track files: {e}")
			return 0
			
	def export_project(self, export_dir, track_manager, audio_engine):
		"""Export project with all audio files to a directory"""
		if self.current_project is None:
			return False
			
		try:
			export_path = Path(export_dir)
			export_path.mkdir(exist_ok=True)
			
			# Save project file in export directory
			project_name = self.current_project['name']
			safe_name = self.make_safe_filename(project_name)
			
			# Copy project file
			project_file = export_path / f"{safe_name}.json"
			with open(project_file, 'w') as f:
				json.dump(self.current_project, f, indent=2)
				
			# Copy audio files for tracks with data
			audio_files_copied = 0
			recordings_folder = Path(self.get_current_recordings_folder())
			
			for track_num in range(1, 9):
				if audio_engine.has_track_data(track_num):
					# Look for the most recent recording file for this track
					safe_project_name = self.make_safe_filename(self.current_project_name)
					patterns = [
						f"{safe_project_name}_track_{track_num}_*.wav",  # New format
						f"track_{track_num}_*.wav"  # Legacy format
					]
					
					latest_file = None
					for pattern in patterns:
						recordings = list(recordings_folder.glob(pattern))
						if recordings:
							# Get the most recent file from this pattern
							pattern_latest = max(recordings, key=lambda p: p.stat().st_mtime)
							if latest_file is None or pattern_latest.stat().st_mtime > latest_file.stat().st_mtime:
								latest_file = pattern_latest
					
					if latest_file:
						dest_file = export_path / f"track_{track_num}.wav"
						shutil.copy2(latest_file, dest_file)
						audio_files_copied += 1
						
			print(f"Project exported to {export_path}")
			print(f"Audio files copied: {audio_files_copied}")
			return True
			
		except Exception as e:
			print(f"Error exporting project: {e}")
			return False
			
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
		
	def get_current_project_info(self):
		"""Get information about current project"""
		if self.current_project is None:
			return None
			
		return {
			'name': self.current_project.get('name', 'Untitled'),
			'created': self.current_project.get('created', ''),
			'modified': self.current_project.get('modified', ''),
			'bpm': self.current_project.get('bpm', 120),
			'track_count': len([t for t in self.current_project.get('tracks', {}).values() 
							   if t.get('has_data', False)])
		}
		
	def cleanup_old_recordings(self, days_to_keep=30):
		"""Clean up old recording files"""
		try:
			cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 3600)
			cleaned_files = 0
			
			# Clean up files in all project recording folders
			for project_folder in self.recordings_dir.iterdir():
				if project_folder.is_dir():
					for audio_file in project_folder.glob("*.wav"):
						if audio_file.stat().st_mtime < cutoff_time:
							audio_file.unlink()
							cleaned_files += 1
			
			# Also clean up any files directly in recordings folder (legacy)
			for audio_file in self.recordings_dir.glob("*.wav"):
				if audio_file.stat().st_mtime < cutoff_time:
					audio_file.unlink()
					cleaned_files += 1
					
			print(f"Cleaned up {cleaned_files} old recording files")
			return cleaned_files
		except Exception as e:
			print(f"Error cleaning up recordings: {e}")
			return 0