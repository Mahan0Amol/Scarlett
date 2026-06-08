import vlc
import asyncio
import os
from pathlib import Path


class MusicAgent:
    def __init__(self, musics_folder):
        self.instance = vlc.Instance()
        self.musics_folder = self.music_folder
        self.player = self.instance.media_player_new()
        self._started = False

    async def find_folders(self, query: str):

        base_dir = self.musics_folder
        matches = []
        for root, dirs, _ in os.walk(base_dir):
            for d in dirs:
                if query.lower() in d.lower():
                    full_path = os.path.join(root, d)
                    matches.append(os.path.normpath(full_path))
        return f"The musics for that query are: {matches}"
    
    async def find_mp3_in_folder(self, folder_path: str):
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            return None
        for file in folder.iterdir():
            if file.is_file() and file.suffix.lower() == ".mp3":
                return str(file.resolve())
        return None

    async def play(self, music_folder: str):
        song_path = await self.find_mp3_in_folder(music_folder)

        if not song_path:
            return "No mp3 files found in the specified folder."

        self.media = self.instance.media_new_path(song_path)
        self.player.set_media(self.media)

        self.player.play()

        print("[MusicAgent Debug] Starting media and buffering...")
        
        
        for i in range(300):  
            await asyncio.sleep(0.1)
            state = self.player.get_state()
            
            if i % 10 == 0:
                print(f"[MusicAgent Debug] VLC State: {state}")

            if state == vlc.State.Playing:
                self._started = True
                print("[MusicAgent Debug] Music is successfully PLAYING now!")
                break
            elif state in (vlc.State.Error, vlc.State.Ended, vlc.State.Stopped):
                print(f"[MusicAgent Debug] Stopped early with state {state}")
                break

    def pause(self):
        self.player.set_pause(1)

    def unpause(self):
        self.player.set_pause(0)

    async def stop(self):
        self.player.stop()

    async def wait_until_end(self):
        while True:
            state = self.player.get_state()
            if state in (vlc.State.Ended, vlc.State.Error, vlc.State.Stopped):
                break
            await asyncio.sleep(0.5)


agent = MusicAgent(musics_folder="E:/Users/aramis/Music")

async def test_music_agent():
    
    await agent.play("E:\\Users\\aramis\\Music\\babymonster_-_clik_clak")
    
    await agent.wait_until_end()


if __name__ == "__main__":
    asyncio.run(test_music_agent())