"""
Track Manager - Manages state of individual tracks
UPDATED to include volume and FX settings
"""

class Track:
	def __init__(self, number):
		self.number = number
		self.is_armed = False
		self.is_muted = False
		self.volume = 1.0
		self.has_data = False
		self.name = f"Track {number}"
		# New properties for FX (not stored here, but tracked for UI)
		
	def arm(self):
		"""Arm track for recording"""
		self.is_armed = True
		
	def disarm(self):
		"""Disarm track from recording"""
		self.is_armed = False
		
	def toggle_mute(self):
		"""Toggle mute state"""
		self.is_muted = not self.is_muted
		return self.is_muted
		
	def set_volume(self, volume):
		"""Set track volume (0.0 to 1.0)"""
		self.volume = max(0.0, min(1.0, volume))
		
	def set_has_data(self, has_data):
		"""Set whether track has recorded data"""
		self.has_data = has_data
		
	def get_state(self):
		"""Get current track state as dictionary"""
		return {
			'number': self.number,
			'name': self.name,
			'is_armed': self.is_armed,
			'is_muted': self.is_muted,
			'volume': self.volume,
			'has_data': self.has_data
		}

class TrackManager:
	def __init__(self, num_tracks=8):
		self.num_tracks = num_tracks
		self.tracks = {}
		self.armed_track = None  # Only one track can be armed at a time
		
		# Initialize tracks
		for i in range(1, num_tracks + 1):
			self.tracks[i] = Track(i)
			
	def get_track(self, track_number):
		"""Get track by number"""
		return self.tracks.get(track_number)
		
	def arm_track(self, track_number):
		"""Arm specific track for recording (disarms others)"""
		# Disarm all tracks first
		for track in self.tracks.values():
			track.disarm()
			
		# Arm the selected track
		if track_number in self.tracks:
			self.tracks[track_number].arm()
			self.armed_track = track_number
			print(f"Armed track {track_number}")
			return True
		return False

		if hasattr(self, '_audio_engine_ref') and self._audio_engine_ref:
			if not self._audio_engine_ref.stream or not self._audio_engine_ref.stream.active:
				self._audio_engine_ref.start_stream()
		
	def disarm_all_tracks(self):
		"""Disarm all tracks"""
		for track in self.tracks.values():
			track.disarm()
		self.armed_track = None
		print("Disarmed all tracks")
		
	def get_armed_track(self):
		"""Get currently armed track number"""
		return self.armed_track
		
	def toggle_track_mute(self, track_number):
		"""Toggle mute for specific track"""
		if track_number in self.tracks:
			is_muted = self.tracks[track_number].toggle_mute()
			print(f"Track {track_number} {'muted' if is_muted else 'unmuted'}")
			return is_muted
		return False
		
	def set_track_volume(self, track_number, volume):
		"""Set volume for specific track"""
		if track_number in self.tracks:
			self.tracks[track_number].set_volume(volume)
			print(f"Track {track_number} volume set to {volume:.2f}")
			
	def mark_track_has_data(self, track_number, has_data=True):
		"""Mark track as having recorded data"""
		if track_number in self.tracks:
			self.tracks[track_number].set_has_data(has_data)
			
	def clear_track(self, track_number):
		"""Clear track data and reset state"""
		if track_number in self.tracks:
			track = self.tracks[track_number]
			track.set_has_data(False)
			track.disarm()
			track.is_muted = False
			track.volume = 1.0
			
			if self.armed_track == track_number:
				self.armed_track = None
				
			print(f"Track {track_number} cleared and reset")
			
	def get_playable_tracks(self):
		"""Get list of tracks that should be played (considering mute only, no solo)"""
		playable = []
		
		# Play all non-muted tracks that have data
		for track_num, track in self.tracks.items():
			if track.has_data and not track.is_muted:
				playable.append(track_num)
					
		return playable
		
	def get_all_track_states(self):
		"""Get state of all tracks"""
		return {num: track.get_state() for num, track in self.tracks.items()}
		
	def has_any_data(self):
		"""Check if any track has recorded data"""
		return any(track.has_data for track in self.tracks.values())
		
	def get_tracks_with_data(self):
		"""Get list of track numbers that have data"""
		return [num for num, track in self.tracks.items() if track.has_data]
		
	def reset_all_tracks(self):
		"""Reset all tracks to default state"""
		for track_num in self.tracks.keys():
			self.clear_track(track_num)
		print("All tracks reset")