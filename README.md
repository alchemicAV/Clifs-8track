# Simple Multitrack Recorder

A user-friendly 8-track audio recorder designed for elderly users who want to record music without complex setup or configuration.

## Features

- **8 Independent Tracks** - Record up to 8 separate audio tracks
- **Simple Interface** - Large buttons and clear labels optimized for accessibility
- **USB Microphone Support** - Automatic detection of USB microphones (tested with Fifine brand)
- **One-Click Recording** - Arm a track and hit record - no complex configuration
- **Basic Mixing Controls** - Mute, Solo, and Clear functions for each track
- **Built-in Metronome** - Adjustable tempo (60-200 BPM)
- **Project Management** - Save and load recording sessions
- **No Advanced Editing** - Focused on simple recording workflow

## System Requirements

- **Windows 10 or 11** (recommended)
- **Python 3.7+** (for source installation)
- **USB Microphone** (any USB audio input device)
- **4GB RAM minimum**
- **1GB free disk space**

## Quick Start (Executable)

1. Download the `MultitrackRecorder.exe` file
2. Double-click to run (no installation needed)
3. Connect your USB microphone
4. Start recording!

## Installation from Source

### Automatic Setup

1. Download all the Python files to a folder
2. **Optional**: Place a `cowbell.mp3` file in the root folder for custom metronome sound
3. Run the setup script:
   ```
   python setup.py
   ```
4. Follow the prompts to install dependencies and create executable

### Manual Setup

1. Install Python dependencies:
   ```
   pip install sounddevice soundfile numpy
   ```

2. Create directories:
   ```
   mkdir recordings projects
   ```

3. Run the application:
   ```
   python main.py
   ```

## How to Use

### Basic Recording Workflow

1. **Connect Microphone** - Plug in your USB microphone
2. **Arm Track** - Click the "ARM" button on the track you want to record to
3. **Start Recording** - Click the main "RECORD" button
4. **Record Your Audio** - Perform into the microphone  
5. **Stop Recording** - Click "RECORD" again to stop
6. **Repeat** - Arm a different track and record additional parts

### Playback Controls

- **PLAY** - Start/pause playback of all recorded tracks
- **STOP** - Stop playback and return to beginning
- **RECORD** - Start/stop recording to the armed track

### Track Controls

Each track has these controls:

- **ARM** - Select this track for recording (only one can be armed at a time)
- **MUTE** - Silence this track during playback
- **SOLO** - Play only this track (mute all others)
- **CLEAR** - Delete the recording from this track (asks for confirmation)

### Metronome

- **ON/OFF** - Enable/disable metronome clicks
- **BPM +/-** - Adjust tempo between 60-200 beats per minute
- The metronome plays during both recording and playback

### Project Management

Projects are automatically saved in the `projects` folder. Audio files are stored in the `recordings` folder.

## Tips for Best Results

1. **Test Your Microphone First** - Arm a track, record a short test, and play it back
2. **Use Headphones** - Prevents microphone from picking up playback audio
3. **Record Dry Signal** - Don't use microphone built-in effects; keep it simple
4. **One Take Per Track** - Recording to an armed track replaces any previous recording
5. **Save Frequently** - Projects auto-save, but manual saves are recommended

## Troubleshooting

### No Audio Input
- Check USB microphone is connected and recognized by Windows
- Try unplugging and reconnecting the microphone
- Check Windows sound settings to ensure microphone is working

### Audio Dropouts
- Close other programs that might use audio
- Try increasing buffer size by restarting the application
- Ensure microphone USB cable is secure

### Application Won't Start
- Verify Python installation and dependencies
- Check that all required files are in the same folder
- Run from command prompt to see error messages

### Poor Audio Quality
- Check microphone positioning (6-12 inches from source)
- Ensure room is reasonably quiet
- Verify microphone is not muted in Windows settings

## File Structure

```
MultitrackRecorder/
├── main.py              # Application entry point
├── audio_engine.py      # Core audio handling
├── track_manager.py     # Track state management
├── ui_controller.py     # User interface
├── project_manager.py   # File management
├── setup.py            # Installation script
├── requirements.txt    # Python dependencies
├── README.md          # This file
├── recordings/        # Audio files directory
└── projects/         # Project files directory
```

## Technical Details

- **Audio Format**: 44.1kHz, 16-bit WAV files
- **Latency**: Optimized for low-latency recording and playback
- **Threading**: Uses separate threads for audio processing and UI updates
- **Memory Usage**: Loads entire tracks into memory for smooth playback

## Limitations

- **No Audio Editing** - This is a recorder, not an editor
- **No Effects** - No reverb, EQ, or other audio processing
- **No MIDI** - Audio recording only, no MIDI support
- **No Punch Recording** - Can't record over specific sections
- **Track Length** - Limited by available system memory

## Support

This software is provided as-is for elderly users who want simple multitrack recording. For technical issues:

1. Check this README for solutions
2. Verify all requirements are met
3. Test with a different USB microphone if available

## License

Free for personal use. Created to help elderly musicians record their music with minimal technical barriers.