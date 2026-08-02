"""
Background task handlers for AudioLoop, split out of Scarlett.py. These run
as asyncio tasks kicked off by plugin tool handlers (see backend/plugins/)
and report their result back to the model via ctx.session.send(...).

Same mixin approach as audio_io.py / video_io.py — see the note in
audio_io.py for why this isn't a fully standalone class yet.
"""

import datetime
import os


class RequestHandlersMixin:
    async def _ensure_project(self, tag):
        """If we're still in the scratch 'temp' project, auto-create and
        switch to a timestamped one. Shared by handle_cad_request and
        handle_write_file, which both used to duplicate this logic."""
        if self.project_manager.current_project != "temp":
            return

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        new_project_name = f"Project_{timestamp}"
        print(f"[scarlett DEBUG] [{tag}] Auto-creating project: {new_project_name}")

        success, msg = self.project_manager.create_project(new_project_name)
        if success:
            self.project_manager.switch_project(new_project_name)
            try:
                await self.session.send(
                    input=f"System Notification: Automatic Project Creation. Switched to new project '{new_project_name}'.",
                    end_of_turn=False,
                )
                if self.on_project_update:
                    self.on_project_update(new_project_name)
            except Exception as e:
                print(f"[scarlett DEBUG] [ERR] Failed to notify auto-project: {e}")

    async def handle_cad_request(self, prompt):
        print(f"[scarlett DEBUG] [CAD] Background Task Started: handle_cad_request('{prompt}')")
        if self.on_cad_status:
            self.on_cad_status("generating")

        await self._ensure_project("CAD")

        cad_output_dir = str(self.project_manager.get_current_project_path() / "cad")
        cad_data = await self.cad_agent.generate_prototype(prompt, output_dir=cad_output_dir)

        if cad_data:
            print("[scarlett DEBUG] [OK] Cscarlettgent returned data successfully.")
            print(
                f"[scarlett DEBUG] [INFO] Data Check: {len(cad_data.get('vertices', []))} vertices, "
                f"{len(cad_data.get('edges', []))} edges."
            )

            if self.on_cad_data:
                self.on_cad_data(cad_data)

            if 'file_path' in cad_data:
                self.project_manager.save_cad_artifact(cad_data['file_path'], prompt)
            else:
                self.project_manager.save_cad_artifact("output.stl", prompt)

            completion_msg = (
                "System Notification: CAD generation is complete! The 3D model is now displayed "
                "for the user. Let them know it's ready."
            )
            try:
                await self.session.send(input=completion_msg, end_of_turn=True)
            except Exception as e:
                print(f"[scarlett DEBUG] [ERR] Failed to send completion notification: {e}")
        else:
            print("[scarlett DEBUG] [ERR] Cscarlettgent returned None.")
            try:
                await self.session.send(input="System Notification: CAD generation failed.", end_of_turn=True)
            except Exception:
                pass

    async def handle_write_file(self, path, content):
        print(f"[scarlett DEBUG] [FS] Writing file: '{path}'")

        await self._ensure_project("FS")

        # Always root the file inside the current project, for safety.
        filename = os.path.basename(path)
        current_project_path = self.project_manager.get_current_project_path()
        final_path = current_project_path / filename
        if not os.path.isabs(path):
            final_path = current_project_path / path

        print(f"[scarlett DEBUG] [FS] Resolved path: '{final_path}'")

        try:
            os.makedirs(os.path.dirname(final_path), exist_ok=True)
            with open(final_path, 'w', encoding='utf-8') as f:
                f.write(content)
            result = f"File '{final_path.name}' written successfully to project '{self.project_manager.current_project}'."
        except Exception as e:
            result = f"Failed to write file '{path}': {str(e)}"

        print(f"[scarlett DEBUG] [FS] Result: {result}")
        await self._notify(result)

    async def handle_read_directory(self, path):
        print(f"[scarlett DEBUG] [FS] Reading directory: '{path}'")
        try:
            if not os.path.exists(path):
                result = f"Directory '{path}' does not exist."
            else:
                items = os.listdir(path)
                result = f"Contents of '{path}': {', '.join(items)}"
        except Exception as e:
            result = f"Failed to read directory '{path}': {str(e)}"

        print(f"[scarlett DEBUG] [FS] Result: {result}")
        await self._notify(result)

    async def handle_read_file(self, path):
        print(f"[scarlett DEBUG] [FS] Reading file: '{path}'")
        try:
            if not os.path.exists(path):
                result = f"File '{path}' does not exist."
            else:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                result = f"Content of '{path}':\n{content}"
        except Exception as e:
            result = f"Failed to read file '{path}': {str(e)}"

        print(f"[scarlett DEBUG] [FS] Result: {result}")
        await self._notify(result)

    async def _notify(self, result):
        """Shared 'tell the model what happened' helper for the FS handlers."""
        try:
            await self.session.send(input=f"System Notification: {result}", end_of_turn=True)
        except Exception as e:
            print(f"[scarlett DEBUG] [ERR] Failed to send fs result: {e}")

    async def handle_web_agent_request(self, prompt):
        print(f"[scarlett DEBUG] [WEB] Web Agent Task: '{prompt}'")

        async def update_frontend(image_b64, log_text):
            if self.on_web_data:
                self.on_web_data({"image": image_b64, "log": log_text})

        result = await self.web_agent.run_task(prompt, update_callback=update_frontend)
        print(f"[scarlett DEBUG] [WEB] Web Agent Task Returned: {result}")

        try:
            await self.session.send(input=f"System Notification: Web Agent has finished.\nResult: {result}", end_of_turn=True)
        except Exception as e:
            print(f"[scarlett DEBUG] [ERR] Failed to send web agent result to model: {e}")
