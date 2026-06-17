import vlc
import asyncio
import os
from pathlib import Path
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
import base64


class MusicAgent:

    _instance = None

    def __new__(cls, musics_folder=None, sio=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    

    def __init__(self, musics_folder, sio):

        if self._initialized:
            return
        
        self._initialized = True

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
        
    def get_current_state(self):
        position = 0

        try:
            length = self.player.get_length()
            if length > 0:
                position = int(self.player.get_time() / 1000)
        except Exception:
            pass

        return {
            **(self.current_metadata or {
                "title": "No Track Selected",
                "artist": "Unknown Artist",
                "duration": 0,
                "thumb": None
            }),
            "position": position,
            "isPlaying": self.player.get_state() == vlc.State.Playing,
            "volume": self.player.audio_get_volume()
        }

    async def search_music(self, fc):

        query = fc.args["query"]

        print(f"[MusicAgent] [find folders] Searching for music with query: '{query}' in folder: '{self.musics_folder}'")

        base_dir = self.musics_folder
        matches = []
        for root, dirs, _ in os.walk(base_dir):
            for d in dirs:
                if query.lower() in d.lower():
                    full_path = os.path.join(root, d)
                    matches.append(os.path.normpath(full_path))
        print(f"[MusicAgent] [find folders] Search query: '{query}' found matches: {matches}")
        return f"The musics for your query are : {matches}"

    async def find_mp3_in_folder(self, folder_path: str):
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            return []
        return [str(f.resolve()) for f in folder.iterdir() if f.is_file() and f.suffix.lower() == ".mp3"]

    async def play(self, fc):

        music_folder = fc.args["track_name"]

        try:

            self.playlist = await self.find_mp3_in_folder(music_folder)
            if not self.playlist:
                return {"error": "No mp3 files found"}

            self.current_index = 0
            self.current_song_path = self.playlist[0]

            self.current_metadata = self.get_metadata(self.current_song_path)

            media = self.instance.media_new_path(self.current_song_path)
            self.player.set_media(media)
            self.player.play()

            await asyncio.sleep(0.2)

            if self.sio:
                await self.sio.emit(
                    "music_state",
                    self.get_current_state()
                )

            # Start auto position updater
            if not hasattr(self, "_tick_task") or self._tick_task is None:
                self._tick_task = asyncio.create_task(self._tick_stream())

            # return self.current_metadata
            return f'Music {self.current_song_path} is playing now'
        except Exception as e:
            return f'There was an error while playing the song: {e}'

    async def _position_updater(self):
        last_emit = 0

        while True:
            try:
                now = asyncio.get_event_loop().time()

                # 10 times per second (smooth UI)
                if self.sio:
                    await self.sio.emit("music_state", {
                        **self.current_metadata,
                        "isPlaying": True
                    })

                await asyncio.sleep(0.05)

            except asyncio.CancelledError:
                break

            except Exception as e:
                print(f"[MusicAgent] Updater error: {e}")
                await asyncio.sleep(1)

    async def _tick_stream(self):
        while True:
            try:
                if self.player and self.player.get_length() > 0:
                    position = self.player.get_time() // 1000
                    duration = self.player.get_length() // 1000

                    if self.sio:
                        await self.sio.emit(
                            "music_tick",
                            {
                                "position": position,
                                "duration": duration,
                                "isPlaying": self.player.get_state() == vlc.State.Playing
                            }
                        )

                await asyncio.sleep(0.25)  # 4 updates per second

            except asyncio.CancelledError:
                break

            except Exception as e:
                print("[MusicAgent tick error]", e)
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

        self.current_song_path = None
        self.current_index = -1
        self.playlist = []

        self.current_metadata = {
            "title": "No Track Selected",
            "artist": "Unknown Artist",
            "duration": 0,
            "thumb": None
        }

    def seek(self, position_seconds: int):
        if self.player.get_length() > 0:
            self.player.set_position(
                position_seconds / (self.player.get_length() / 1000)
            )

        if self.sio:
            asyncio.create_task(
                self.sio.emit(
                    "music_state",
                    self.get_current_state()
                )
            )

    def set_volume(self, volume: int):
        self.player.audio_set_volume(max(0, min(100, volume)))

    async def handle_control_music(self, fc):
        action = fc.args["action"]

        if action == 'pause':
            try:
                self.pause()

                if self.sio:
                    await self.sio.emit(
                        "music_state",
                        self.get_current_state()
                    )

                return 'Music paused successfully'

            except Exception as e:
                return f'There was an error when pausing the music : {e}'
            
        elif action == 'unpause':
            try:
                self.unpause()

                if self.sio:
                    await self.sio.emit(
                        "music_state",
                        self.get_current_state()
                    )

                return 'Music resumed successfully'

            except Exception as e:
                return f'There was an error when unpausing the music : {e}'
            
        elif action == 'next':
            try:

                self.current_metadata = self.next_track()

                await asyncio.sleep(0.15)

                if self.sio:
                    await self.sio.emit(
                        "music_state",
                        self.get_current_state()
                    )

                return 'Next track played successfully'

            except Exception as e:
                return f'There was an error when playing next track: {e}'


        elif action == 'previous':
            try:

                self.current_metadata = self.prev_track()

                await asyncio.sleep(0.15)

                if self.sio:
                    await self.sio.emit(
                        "music_state",
                        self.get_current_state()
                    )

                return 'Previous track played successfully'

            except Exception as e:
                return f'There was an error when playing previous track: {e}'




    async def handle_function_call(self, fc):
        func_map = {
            "search_music": self.search_music,
            "play_music": self.play,
            "control_music": self.handle_control_music,
        }

        func = func_map.get(fc.name)

        print(f"[MusicAgent] Received function call: '{fc.name}' with args: {fc.args}")

        if not func:
            print(f"[MusicAgent] Unknown function call: {fc.name}")
            return None

        return await func(fc)


async def _demo():
    # Example usage
    agent = MusicAgent("E:/Users/aramis/Music", None)
    class FC:
        def __init__(self, name, args):
            self.name = name
            self.args = args

    search_fc = FC("play_music", {"track_name": "E:\\Users\\aramis\\Music\\Monster - Eminem"})
    print(await agent.handle_function_call(search_fc))

if __name__ == "__main__":
    asyncio.run(_demo())