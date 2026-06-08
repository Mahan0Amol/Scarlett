import vlc
import asyncio
import os
from pathlib import Path
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
import base64


class MusicAgent:
    def __init__(self, musics_folder, sio):
        self.instance = vlc.Instance()
        self.musics_folder = musics_folder
        self.sio = sio  # Socket.IO instance for emitting updates
        self.player = self.instance.media_player_new()
        self.current_song_path = None
        self.playlist = []
        self.current_index = -1
        self._update_task = None
        self.current_metadata = None

    def get_metadata(self, song_path: str):
        if not os.path.exists(song_path):
            return {"title": Path(song_path).stem, "artist": "Unknown Artist", "duration": 0, "thumb": None}

        try:
            audio = MP3(song_path)
            tags = ID3(song_path)

            title = tags.get("TIT2").text[0] if tags and tags.get("TIT2") else Path(song_path).stem
            artist = tags.get("TPE1").text[0] if tags and tags.get("TPE1") else "Unknown Artist"
            duration = int(audio.info.length)

            thumb_b64 = None
            if tags:
                for key in tags.keys():
                    if key.startswith("APIC"):
                        thumb_b64 = base64.b64encode(tags[key].data).decode('utf-8')
                        break

            return {
                "title": str(title),
                "artist": str(artist),
                "duration": duration,
                "thumb": f"data:image/jpeg;base64,{thumb_b64}" if thumb_b64 else None
            }
        except Exception:
            return {
                "title": Path(song_path).stem,
                "artist": "Unknown Artist",
                "duration": 0,
                "thumb": None
            }

    async def find_mp3_in_folder(self, folder_path: str):
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            return []
        return [str(f.resolve()) for f in folder.iterdir() if f.is_file() and f.suffix.lower() == ".mp3"]

    async def play(self, music_folder: str):
        self.playlist = await self.find_mp3_in_folder(music_folder)
        if not self.playlist:
            return {"error": "No mp3 files found"}

        self.current_index = 0
        self.current_song_path = self.playlist[0]

        self.current_metadata = self.get_metadata(self.current_song_path)

        media = self.instance.media_new_path(self.current_song_path)
        self.player.set_media(media)
        self.player.play()

        # Start auto position updater
        if self._update_task:
            self._update_task.cancel()
        self._update_task = asyncio.create_task(self._position_updater())

        return self.current_metadata

    async def _position_updater(self):
        """Send live position updates every 500ms"""
        while True:
            try:
                if self.player.get_state() == vlc.State.Playing and self.sio:
                    position = int(self.player.get_position() * (self.player.get_length() / 1000)) if self.player.get_length() > 0 else 0
                    try:    
                        await self.sio.emit('music_state', {
                            **self.current_metadata,
                            "position": position,
                            "isPlaying": True
                        })
                    except Exception as e:
                        print(f"[MusicAgent] Socket emit error: {e}")
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[MusicAgent] Updater error: {e}")
                await asyncio.sleep(1)

    def next_track(self):
        if not self.playlist:
            return None
        self.current_index = (self.current_index + 1) % len(self.playlist)
        self.current_song_path = self.playlist[self.current_index]
        media = self.instance.media_new_path(self.current_song_path)
        self.player.set_media(media)
        self.player.play()
        return self.get_metadata(self.current_song_path)  # Returns dict (sync)

    def prev_track(self):
        if not self.playlist:
            return None
        self.current_index = (self.current_index - 1) % len(self.playlist)
        self.current_song_path = self.playlist[self.current_index]
        media = self.instance.media_new_path(self.current_song_path)
        self.player.set_media(media)
        self.player.play()
        return self.get_metadata(self.current_song_path)

    def pause(self):
        self.player.set_pause(1)

    def unpause(self):
        self.player.set_pause(0)

    def stop(self):
        if self._update_task:
            self._update_task.cancel()
        self.player.stop()

    def seek(self, position_seconds: int):
        if self.player.get_length() > 0:
            self.player.set_position(position_seconds / (self.player.get_length() / 1000))

    def set_volume(self, volume: int):
        self.player.audio_set_volume(max(0, min(100, volume)))