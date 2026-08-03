"""
Audio input/output for AudioLoop, split out of Scarlett.py.

This is a mixin (not a standalone class) because it's tightly coupled to
AudioLoop's shared runtime state (self.session, self.out_queue,
self.audio_in_queue, self.paused, VAD state, etc). Splitting it into a truly
independent class would mean threading all of that state through a second
object — a bigger, riskier rewrite. This is the pragmatic first step:
same behaviour, physically separate file, one clear responsibility.
"""

import asyncio
import base64
import math
import struct
import time

from .audio_config import FORMAT, CHANNELS, SEND_SAMPLE_RATE, RECEIVE_SAMPLE_RATE, CHUNK_SIZE, pya

# VAD (voice activity detection) tuning
VAD_THRESHOLD = 800        # Adjust based on mic sensitivity (800 is conservative for 16-bit)
SILENCE_DURATION = 0.5     # Seconds of silence before considering the user "done speaking"


class AudioIOMixin:
    def clear_audio_queue(self):
        """Clears the queue of pending audio chunks to stop playback immediately."""
        try:
            count = 0
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()
                count += 1
            if count > 0:
                print(f"[scarlett DEBUG] [AUDIO] Cleared {count} chunks from playback queue due to interruption.")
        except Exception as e:
            print(f"[scarlett DEBUG] [ERR] Failed to clear audio queue: {e}")

    async def send_frame(self, frame_data):
        if isinstance(frame_data, bytes):
            b64_data = base64.b64encode(frame_data).decode('utf-8')
        else:
            b64_data = frame_data

        # Store as the designated "next frame to send"; listen_audio pulls it.
        self._latest_image_payload = {"mime_type": "image/jpeg", "data": b64_data}

    async def send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send(input=msg, end_of_turn=False)

    def _resolve_input_device_index(self):
        """Resolves the mic to use: by name, then by index, then default."""
        if self.input_device_name:
            print(f"[scarlett] Attempting to find input device matching: '{self.input_device_name}'")
            count = pya.get_device_count()
            for i in range(count):
                try:
                    info = pya.get_device_info_by_index(i)
                    if info['maxInputChannels'] > 0:
                        name = info.get('name', '')
                        if self.input_device_name.lower() in name.lower() or name.lower() in self.input_device_name.lower():
                            print(f"   Candidate {i}: {name}")
                            print(f"[scarlett] Resolved input device '{self.input_device_name}' to index {i} ({name})")
                            return i
                except Exception:
                    continue
            print(f"[scarlett] Could not find device matching '{self.input_device_name}'. Checking index...")

        if self.input_device_index is not None:
            try:
                resolved = int(self.input_device_index)
                print(f"[scarlett] Requesting Input Device Index: {resolved}")
                return resolved
            except ValueError:
                print(f"[scarlett] Invalid device index '{self.input_device_index}', reverting to default.")

        print("[scarlett] Using Default Input Device")
        return None

    async def listen_audio(self):
        mic_info = pya.get_default_input_device_info()
        resolved_input_device_index = self._resolve_input_device_index()

        try:
            self.audio_stream = await asyncio.to_thread(
                pya.open,
                format=FORMAT,
                channels=CHANNELS,
                rate=SEND_SAMPLE_RATE,
                input=True,
                input_device_index=resolved_input_device_index if resolved_input_device_index is not None else mic_info["index"],
                frames_per_buffer=CHUNK_SIZE,
            )
        except OSError as e:
            print(f"[scarlett] [ERR] Failed to open audio input stream: {e}")
            print("[scarlett] [WARN] Audio features will be disabled. Please check microphone permissions.")
            return

        kwargs = {"exception_on_overflow": False} if __debug__ else {}

        while True:
            if self.paused:
                await asyncio.sleep(0.1)
                continue

            try:
                data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)

                if self.out_queue:
                    await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})

                await self._run_vad(data)

            except Exception as e:
                print(f"Error reading audio: {e}")
                await asyncio.sleep(0.1)

    async def _run_vad(self, data):
        """Simple RMS-based voice activity detection: sends one video frame
        the moment speech starts, and resets state after a period of silence."""
        count = len(data) // 2
        if count > 0:
            shorts = struct.unpack(f"<{count}h", data)
            sum_squares = sum(s ** 2 for s in shorts)
            rms = int(math.sqrt(sum_squares / count))
        else:
            rms = 0

        if rms > VAD_THRESHOLD:
            self._silence_start_time = None

            if not self._is_speaking:
                self._is_speaking = True
                print(f"[scarlett DEBUG] [VAD] Speech Detected (RMS: {rms}). Sending Video Frame.")
                if self._latest_image_payload and self.out_queue:
                    await self.out_queue.put(self._latest_image_payload)
                else:
                    print("[scarlett DEBUG] [VAD] No video frame available to send.")
        else:
            if self._is_speaking:
                if self._silence_start_time is None:
                    self._silence_start_time = time.time()
                elif time.time() - self._silence_start_time > SILENCE_DURATION:
                    print("[scarlett DEBUG] [VAD] Silence detected. Resetting speech state.")
                    self._is_speaking = False
                    self._silence_start_time = None

    async def play_audio(self):
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
            output_device_index=self.output_device_index,
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            self.emit("audio_data", {"data": list(bytestream)})
            await asyncio.to_thread(stream.write, bytestream)
