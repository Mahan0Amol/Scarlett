"""Shared audio config used by AudioIOMixin. Kept separate so both
Scarlett.py and audio_io.py can import it without circular imports."""

import pyaudio

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

pya = pyaudio.PyAudio()
