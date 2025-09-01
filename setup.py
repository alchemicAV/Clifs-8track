#!/usr/bin/env python3
"""
Setup script for Simple Multitrack Recorder
Handles dependency installation and executable creation
"""

import subprocess
import sys
import os
from pathlib import Path

def install_dependencies():
	"""Install required Python packages"""
	print("Installing dependencies...")
	
	packages = [
		"sounddevice>=0.4.6",
		"soundfile>=0.12.1", 
		"numpy>=1.21.0",
		"scipy>=1.7.0"
	]
	
	for package in packages:
		try:
			subprocess.check_call([sys.executable, "-m", "pip", "install", package])
			print(f"✓ Installed {package}")
		except subprocess.CalledProcessError as e:
			print(f"✗ Failed to install {package}: {e}")
			return False
	
	print("Dependencies installed successfully!")
	return True

def create_executable():
	"""Create standalone executable using PyInstaller"""
	print("Creating standalone executable...")
	
	# Check if PyInstaller is available
	try:
		import PyInstaller
	except ImportError:
		print("Installing PyInstaller...")
		try:
			subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
		except subprocess.CalledProcessError:
			print("✗ Failed to install PyInstaller")
			return False
	
	# Build list of additional data files
	add_data_args = []
	
	# Include deer.jpg if it exists
	if Path("deer.jpg").exists():
		if os.name == 'nt':  # Windows
			add_data_args.extend(["--add-data", "deer.jpg;."])
		else:  # Unix/Linux/Mac
			add_data_args.extend(["--add-data", "deer.jpg:."])
		print("✓ Including deer.jpg in executable")
	
	# Include audio files if they exist
	for audio_file in ["cowbell.mp3", "and1.mp3"]:
		if Path(audio_file).exists():
			if os.name == 'nt':  # Windows
				add_data_args.extend(["--add-data", f"{audio_file};."])
			else:  # Unix/Linux/Mac  
				add_data_args.extend(["--add-data", f"{audio_file}:."])
			print(f"✓ Including {audio_file} in executable")
	
	# PyInstaller command
	cmd = [
		sys.executable, "-m", "PyInstaller",
		"--onefile",
		"--windowed", 
		"--name", "MultitrackRecorder",
		*add_data_args,
		"main.py"
	]
	
	try:
		subprocess.check_call(cmd)
		print("✓ Executable created successfully!")
		print("✓ Find MultitrackRecorder.exe in the 'dist' folder")
		return True
	except subprocess.CalledProcessError as e:
		print(f"✗ Failed to create executable: {e}")
		return False

def create_directories():
	"""Create necessary directories"""
	dirs = ["recordings", "projects"]
	
	for dir_name in dirs:
		Path(dir_name).mkdir(exist_ok=True)
		print(f"✓ Created directory: {dir_name}")

def check_system_requirements():
	"""Check if system meets requirements"""
	print("Checking system requirements...")
	
	# Check Python version
	if sys.version_info < (3, 7):
		print("✗ Python 3.7 or higher is required")
		return False
	else:
		print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor} detected")
	
	# Check if running on Windows (recommended)
	if os.name != 'nt':
		print("⚠ This application is optimized for Windows")
		print("  Audio functionality may vary on other platforms")
	else:
		print("✓ Windows platform detected")
	
	return True

def main():
	"""Main setup function"""
	print("=" * 50)
	print("Simple Multitrack Recorder Setup")
	print("=" * 50)
	
	if not check_system_requirements():
		return False
	
	print("\n1. Creating directories...")
	create_directories()
	
	print("\n2. Installing dependencies...")
	if not install_dependencies():
		return False
	
	print("\n3. Setup complete!")
	print("\nTo run the application:")
	print("  python main.py")
	
	# Ask if user wants to create executable
	create_exe = input("\nCreate standalone executable? (y/n): ").lower().strip()
	if create_exe in ['y', 'yes']:
		print("\n4. Creating executable...")
		create_executable()
	
	print("\n" + "=" * 50)
	print("Setup completed successfully!")
	print("=" * 50)
	
	return True

if __name__ == "__main__":
	try:
		success = main()
		if not success:
			sys.exit(1)
	except KeyboardInterrupt:
		print("\nSetup cancelled by user")
		sys.exit(1)
	except Exception as e:
		print(f"\nUnexpected error during setup: {e}")
		sys.exit(1)