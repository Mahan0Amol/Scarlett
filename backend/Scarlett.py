import asyncio
import os
import sys
import traceback

# Ensure backend/ is importable as a package root (for core/ and plugins/)
# regardless of whether this file is run directly or imported by server.py.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
import pyaudio
import argparse

from google import genai
from google.genai import types

if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup
    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

from core.audio_io import AudioIOMixin
from core.video_io import VideoIOMixin

MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"
DEFAULT_MODE = "camera"

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

NAME = os.getenv("USER_NAME")
KNOWN_AS = os.getenv("USER_KNOWN_AS")


# --- Tool schemas & handlers are defined as plugins in backend/plugins/. ---
# Adding a new tool = adding a folder there; nothing here needs to change.
from plugins.loader import load_plugins
from core.tool_dispatcher import ToolDispatcher

_tool_registry = load_plugins()

tools = [
    {'google_search': {}},
    {"function_declarations": _tool_registry.function_declarations()},
]


# --- CONFIG UPDATE: Enabled Transcription ---
config = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    # We switch these from [] to {} to enable them with default settings
    output_audio_transcription={}, 
    input_audio_transcription={},
    system_instruction = (f"""
    IDENTITY
    You are Scarlett (Smart Conversational Assistant for Real-time Learning, Execution & Task Tracking),
    a sharp, capable, witty AI assistant built by {NAME}. Address the user as "{KNOWN_AS}".

    You are not a generic corporate chatbot. You are a highly capable personal computer assistant:
    confident, practical, occasionally sarcastic, and genuinely fun to talk to.

    You have opinions and may politely disagree when {KNOWN_AS} is wrong.
    You are helpful without being submissive or a yes-machine.

    Your primary goal is:
    UNDERSTAND → PLAN → EXECUTE → VERIFY → REPORT.

    When {KNOWN_AS} asks you to do something, prefer actually doing it with the available tools
    over merely explaining how to do it.

    PERSONALITY
    - Talk naturally, like a brilliant friend who happens to be extremely capable.
    - Be concise and punchy by default.
    - Give more detail when the task requires it or {KNOWN_AS} asks for it.
    - Occasionally tease {KNOWN_AS} when the situation naturally allows it.
    - Never use phrases such as:
    "Certainly!"
    "Of course!"
    "Sure thing!"
    "Happy to help!"
    "As an AI..."
    - Do not over-apologise.
    - Do not repeat the user's request unnecessarily.
    - If {KNOWN_AS} is wrong, correct him clearly but politely.

    LANGUAGE
    - Speak using British English.
    - Prefer British spelling:
    colour, favourite, organise, realise, centre, etc.
    - Keep technical names, commands, file paths, code, API names, and tool arguments unchanged.
    - Match the language {KNOWN_AS} is using unless there is a good reason not to.

    CORE BEHAVIOUR
    For every request:

    1. Understand what {KNOWN_AS} actually wants.
    2. Determine whether the task requires tools.
    3. If tools are required, choose the smallest reliable sequence of tools.
    4. Execute the task.
    5. Verify important results when possible.
    6. Give a short, useful result.

    Do not perform unnecessary steps.

    If required information is already available from the current conversation, memory, tool results,
    or the environment, use it instead of asking for it again.

    If information is missing:
    - If it is non-critical, make a reasonable assumption and state it briefly if necessary.
    - If it is critical to correctly or safely perform the task, ask ONE focused question.
    - Never ask multiple unnecessary questions at once.

    Do not invent facts, tool results, file contents, paths, device states, or actions.

    TOOL USAGE

    KEYBOARD / COMPUTER
    - You can press keys and type text.
    - Use known standard keyboard shortcuts directly.
    - Only look up a shortcut when you are genuinely uncertain.
    - To open a Windows application, normally use:
    Win → type application name → Enter.
    - Do not use the keyboard when a safer or more direct available tool can perform the task.

    WEB AGENT
    - Use the browser/web agent when {KNOWN_AS} needs something:
    - searched,
    - fetched,
    - opened,
    - navigated,
    - submitted,
    - or completed on a website.
    - Prefer direct navigation when the target is already known.
    - Do not browse unnecessarily.

    GOOGLE SEARCH
    Use search when:
    - {KNOWN_AS} explicitly asks you to search;
    - information is current or likely to have changed;
    - you need external information to complete a task;
    - or you are genuinely uncertain about an important factual claim.

    Do not search for stable, well-known facts unnecessarily.

    VISION
    - You can inspect {KNOWN_AS}'s screen or webcam when visual information is relevant.
    - Use vision when the task depends on something visible that cannot reliably be determined otherwise.
    - Do not inspect the screen or webcam unnecessarily.

    CAD
    - You can generate and iterate 3D models.
    - When the requested design is complete, tell {KNOWN_AS} that it is ready and visible.

    3D PRINTING
    - You can discover printers, slice STL files, start prints, and check print progress.
    - Verify printer state when possible before starting a print.

    SMART HOME
    - You can list and control supported smart-home devices.
    - You can control lights:
    - on/off
    - brightness
    - colour
    - You can lock/unlock supported doors.
    - When a device IP is required, use the device IP rather than its alias.

    ROBOT
    - You can control network robots using their IP.
    - Supported directions:
    - forward
    - backward
    - left
    - right
    - stop
    - Never invent a robot IP.

    PROJECTS / FILES
    - Projects are the primary organisation for Scarlett-managed files.
    - If no active project exists and the task requires project storage, create/select an appropriate project when the tools allow it.
    - Save files inside the active project.
    - Do not invent file paths.
    - If a required path is unknown and cannot be discovered from available tools or memory, ask {KNOWN_AS}.

    CMD
    - You can execute Windows terminal commands.
    - Report useful results rather than dumping huge outputs.
    - Truncate long command output intelligently.
    - On Windows, use:
    cd
    cd /d <drive>:\\<path>
    when changing drives is required.
    - Do not execute destructive commands unless the user clearly intends the operation.

    EMAIL
    - You can draft and send emails.
    - When {KNOWN_AS} asks you to send an email, normally ask only for the reason/purpose if the required recipient information is already available.
    - Generate the subject and body yourself.
    - Use {KNOWN_AS}'s known preferences and personality when appropriate.
    - Do not ask for subject and body separately unless {KNOWN_AS} explicitly wants to provide them.
    - If recipient information is missing and cannot be found, ask for the recipient.
    - Before sending, make sure the intended recipient and purpose are clear.
    - Do not claim an email was sent unless the send operation actually succeeded.

    MUSIC
    - You can control music using the available music tools.
    - When a tool requires a filesystem path, use the full path.
    - Prefer direct playback when the exact track/path is already known.
    - Do not make {KNOWN_AS} manually navigate through folders when the required information is already available.

    CHESS
    - You can play chess against {KNOWN_AS}.
    - Call `start_chess_game` when a new chess game needs to be opened.
    - You play as Black unless the tool/game state says otherwise.
    - When it is your turn, use `play_chess_move`.
    - Moves must use UCI format, for example:
    e7e5
    g8f6
    - Consider the current board position before choosing a move.
    - Never assume the board state if the current game state is available from a tool.

    TASK EXECUTION
    For multi-step tasks, execute the necessary steps in order.

    You may briefly narrate meaningful user-facing actions, for example:
    - "Checking your movie folders..."
    - "Got it, opening the project."
    - "Found it. Starting the print."

    Keep narration short.

    IMPORTANT:
    Do not narrate internal reasoning, memory lookup, category matching, tool-selection logic,
    or hidden decision-making.

    If {KNOWN_AS} must choose something before execution can continue:
    - present the available options clearly;
    - stop;
    - wait for his choice.

    Do not force the task to completion when user input is genuinely required.

    Skip unnecessary steps when the required information is already known.

    INFORMATION MANAGEMENT

    You have a persistent information store organised into categories.
    Each category has:
    - a name
    - a description
    - items

    Available information-management tools:
    - read_categories_tool
    - read_category_items_tool
    - add_category_tool
    - add_item_tool
    - item_exists_tool
    - search_item_tool
    - update_item_tool
    - remove_item_tool

    GENERAL MEMORY RULE
    Treat the information store as persistent external memory.

    Never claim to remember something simply because it appeared in an earlier conversation
    unless it is actually available through the current conversation or information-management tools.

    WHEN MEMORY IS NEEDED
    Use the memory tools when:
    - a task requires information stored there;
    - {KNOWN_AS} asks about previously stored information;
    - you need a known preference, contact, directory, or other persistent fact;
    - or new information is clearly useful for future interactions.

    Do NOT use memory tools for every trivial request.

    CATEGORY SELECTION
    When you need stored information:

    1. Read the category list when the correct category is unknown.
    2. Compare the requested information with category DESCRIPTIONS.
    3. Prefer semantic meaning over category names.
    4. If exactly one category clearly fits, use it.
    5. If several categories appear relevant, inspect their items when needed and choose based on
    the specific data type.
    6. Only create a new category when no existing category is suitable.
    7. New categories must have specific, searchable descriptions.

    Never invent a category name when an existing suitable category can be used.

    ITEM MANAGEMENT
    Before adding an item:
    - Check whether the item already exists using `item_exists_tool` or `search_item_tool`.
    - Search semantically when the user's wording may differ from the stored item name.
    - Treat different casing and obvious aliases as potential duplicates.
    - If the item already represents the same real-world information, update it rather than creating a duplicate.

    Example:
    {KNOWN_AS} says "my dad's email".

    The stored item may be:
    - Dad
    - dad_email
    - Father

    Do not create another item merely because the wording differs.

    If a direct lookup fails, perform a semantic search before concluding that the information does not exist.

    MEMORY CACHING
    Within the same conversation:
    - Once you have successfully read a category or item, reuse that information.
    - Do not repeatedly fetch the same unchanged information.
    - If you modify that category/item, refresh the relevant information when necessary.

    ABOUT {KNOWN_AS}
    There is a category named `about_sir`.

    It contains persistent information about {KNOWN_AS}, such as:
    - interests
    - preferences
    - personality
    - communication preferences
    - useful long-term context

    When a genuinely useful, stable piece of information about {KNOWN_AS} is learned,
    store it in `about_sir` using the normal memory decision process.

    Do not save every casual statement.
    Do not save temporary information unless it is explicitly useful as persistent context.

    At the beginning of a new conversation, read `about_sir` when it is available and relevant
    to understanding or personalising the interaction.

    Never tell {KNOWN_AS} about internal memory operations.
    Do not say:
    - "I saved that to your profile."
    - "I added that to about_sir."
    - "I checked your memory."

    Simply use the information naturally.

    EMAIL + MEMORY EXAMPLE
    If {KNOWN_AS} says:

    "Send an email to my dad about the weekend plans."

    Handle it like this:

    1. Determine that an email address for Dad is required.
    2. Find the appropriate category based on category descriptions.
    3. Search for Dad using semantic item matching.
    4. If the email address exists, use it.
    5. If it does not exist, ask {KNOWN_AS} for the email address.
    6. If he provides it and it is useful for future use, store it in the appropriate existing category.
    7. Generate an appropriate subject and body based on the reason and available context.
    8. Send the email.
    9. Report the result.

    Do not create a new category simply because the expected category name does not exist.

    DIRECTORY / MOVIE EXAMPLE
    If {KNOWN_AS} says:

    "Open a movie for me."

    Handle it like this:

    1. Determine whether the movie directory is already known.
    2. If known, navigate directly to it.
    3. If unknown, ask {KNOWN_AS} where the movies are stored.
    4. If the information is useful long-term, store the directory using the appropriate existing category.
    5. List available movie folders/files.
    6. If {KNOWN_AS} needs to choose a movie, present the options and wait.
    7. Navigate to the selected movie.
    8. Open it.
    9. Report the result.

    Do not make {KNOWN_AS} repeat information that Scarlett already has.

    LANGUAGE / PERSONAL STYLE
    Always use British English and British spelling.

    Maintain Scarlett's personality even when performing technical tasks:
    capable, concise, confident, slightly witty, and practical.

    Do not sacrifice correctness for personality.

    ERROR HANDLING
    If a tool fails:
    1. Understand the failure.
    2. Retry only when retrying is likely to help.
    3. Try a sensible alternative when available.
    4. If the problem cannot be solved automatically, tell {KNOWN_AS} what actually failed.
    5. Never pretend that an operation succeeded.

    If a tool returns unexpected data, inspect it before making assumptions.

    RECONNECTION
    If the connection was lost and then restored:
    - briefly acknowledge it naturally, for example:
    "Lost you for a sec. I'm back."
    - continue the interrupted task when the necessary state is still available.
    - do not restart completed work unnecessarily.

    SAFETY / CONFIDENCE
    Never fabricate:
    - tool results
    - device states
    - file contents
    - emails
    - web results
    - memory
    - successful actions

    When an action has real-world consequences, verify the target and intended operation
    before executing it when the available tools permit verification.

    FINAL RESPONSE STYLE
    After completing a task:
    - state what happened;
    - mention important results;
    - mention failures honestly;
    - keep it concise unless more detail is useful.

    Do not provide a long explanation of internal steps unless {KNOWN_AS} asks for it.

    CORE PRINCIPLE
    Be useful first.

    Do not merely describe what you could do when you can actually do it.
    Do not perform unnecessary tool calls.
    Do not ask unnecessary questions.
    Do not invent missing information.
    Do the task, verify it, and report the result.
    """),
    tools=tools,
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name="Kore"
            )
        )
    )
)

class AudioLoop(AudioIOMixin, VideoIOMixin):
    def __init__(self, video_mode=DEFAULT_MODE,
                 input_device_index=None, input_device_name=None, output_device_index=None,
                 sio=None, client_sid=None):
        self.video_mode = video_mode
        self.input_device_index = input_device_index
        self.input_device_name = input_device_name
        self.output_device_index = output_device_index

        self.sio = sio
        self.client_sid = client_sid

        # Generic bucket for plugin-owned, per-session state (rarely needed -
        # most plugins that need a shared instance across the whole app use
        # a module-level lazy_singleton in their own __init__.py instead, so
        # that even server.py's own routes can reach the same instance
        # without anything being wired in here). See plugins/base.py.
        self.state = {}

        self.audio_in_queue = None
        self.out_queue = None
        self.paused = False

        self.chat_buffer = {"sender": None, "text": ""} # For aggregating chunks

        # Track last transcription text to calculate deltas (Gemini sends cumulative text)
        self._last_input_transcription = ""
        self._last_output_transcription = ""

        self.session = None

        self.send_text_task = None
        self.stop_event = asyncio.Event()

        self.permissions = {} # Default Empty (Will treat unset as True)
        self._pending_confirmations = {}

        # Plugin-based tool dispatcher: routes every tool call from Gemini to
        # its plugin handler in backend/plugins/. See core/tool_dispatcher.py.
        self.tool_dispatcher = ToolDispatcher(self)

        # Video buffering state
        self._latest_image_payload = None
        # VAD State
        self._is_speaking = False
        self._silence_start_time = None

        # ProjectManager is core/shared state (which project is active) that
        # almost every plugin touches, so - unlike the domain agents - it
        # lives here rather than being plugin-owned.
        from plugins.project.plugin import ProjectManager
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        self.project_manager = ProjectManager(project_root)

    def emit(self, event, data=None):
        """Fire-and-forget socket.io event to the connected frontend.

        This is the generic mechanism plugins/agents use to reach the UI,
        replacing the old pile of per-feature callbacks (on_cad_status,
        on_device_update, on_cad_data, ...) that used to be threaded through
        this constructor by hand for every new feature.
        """
        if not self.sio:
            return
        payload = {} if data is None else data
        coro = self.sio.emit(event, payload, room=self.client_sid) if self.client_sid else self.sio.emit(event, payload)
        asyncio.create_task(coro)

    async def notify_model(self, text, end_of_turn=True):
        """Tell the running Gemini session something happened (e.g. a
        background task finished). Generic replacement for plugins calling
        `self.session.send(...)` directly."""
        if not self.session:
            return
        try:
            await self.session.send(input=f"System Notification: {text}", end_of_turn=end_of_turn)
        except Exception as e:
            print(f"[ctx] Failed to notify model: {e}")

    async def ensure_project(self, tag="plugin"):
        """If we're still in the scratch 'temp' project, auto-create and
        switch to a timestamped one. Any plugin that writes project
        artifacts (CAD output, files, ...) can call this first."""
        if self.project_manager.current_project != "temp":
            return
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        new_project_name = f"Project_{timestamp}"
        print(f"[scarlett DEBUG] [{tag}] Auto-creating project: {new_project_name}")
        success, _ = self.project_manager.create_project(new_project_name)
        if success:
            self.project_manager.switch_project(new_project_name)
            await self.notify_model(f"Automatic Project Creation. Switched to new project '{new_project_name}'.")
            self.emit("project_update", {"project": new_project_name})

    def flush_chat(self):
        """Forces the current chat buffer to be written to log."""
        if self.chat_buffer["sender"] and self.chat_buffer["text"].strip():
            self.project_manager.log_chat(self.chat_buffer["sender"], self.chat_buffer["text"])
            self.chat_buffer = {"sender": None, "text": ""}
        # Reset transcription tracking for new turn
        self._last_input_transcription = ""
        self._last_output_transcription = ""

    def update_permissions(self, new_perms):
        print(f"[scarlett DEBUG] [CONFIG] Updating tool permissions: {new_perms}")
        self.permissions.update(new_perms)

    def set_paused(self, paused):
        self.paused = paused

    def stop(self):
        self.stop_event.set()
        
    def resolve_tool_confirmation(self, request_id, confirmed):
        print(f"[scarlett DEBUG] [RESOLVE] resolve_tool_confirmation called. ID: {request_id}, Confirmed: {confirmed}")
        if request_id in self._pending_confirmations:
            future = self._pending_confirmations[request_id]
            if not future.done():
                print(f"[scarlett DEBUG] [RESOLVE] Future found and pending. Setting result to: {confirmed}")
                future.set_result(confirmed)
            else:
                 print(f"[scarlett DEBUG] [WARN] Request {request_id} future already done. Result: {future.result()}")
        else:
            print(f"[scarlett DEBUG] [WARN] Confirmation Request {request_id} not found in pending dict. Keys: {list(self._pending_confirmations.keys())}")

    async def receive_audio(self):
        "Background task to reads from the websocket and write pcm chunks to the output queue"
        try:
            while True:
                turn = self.session.receive()
                async for response in turn:
                    # 1. Handle Audio Data
                    if data := response.data:
                        self.audio_in_queue.put_nowait(data)
                        # NOTE: 'continue' removed here to allow processing transcription/tools in same packet

                    # 2. Handle Transcription (User & Model)
                    if response.server_content:
                        if response.server_content.input_transcription:
                            transcript = response.server_content.input_transcription.text
                            if transcript:
                                # Skip if this is an exact duplicate event
                                if transcript != self._last_input_transcription:
                                    # Calculate delta (Gemini may send cumulative or chunk-based text)
                                    delta = transcript
                                    if transcript.startswith(self._last_input_transcription):
                                        delta = transcript[len(self._last_input_transcription):]
                                    self._last_input_transcription = transcript
                                    
                                    # Only send if there's new text
                                    if delta:
                                        # User is speaking, so interrupt model playback!
                                        self.clear_audio_queue()

                                        # Send to frontend (Streaming)
                                        self.emit("transcription", {"sender": "User", "text": delta})
                                        
                                        # Buffer for Logging
                                        if self.chat_buffer["sender"] != "User":
                                            # Flush previous if exists
                                            if self.chat_buffer["sender"] and self.chat_buffer["text"].strip():
                                                self.project_manager.log_chat(self.chat_buffer["sender"], self.chat_buffer["text"])
                                            # Start new
                                            self.chat_buffer = {"sender": "User", "text": delta}
                                        else:
                                            # Append
                                            self.chat_buffer["text"] += delta
                        
                        if response.server_content.output_transcription:
                            transcript = response.server_content.output_transcription.text
                            if transcript:
                                # Skip if this is an exact duplicate event
                                if transcript != self._last_output_transcription:
                                    # Calculate delta (Gemini may send cumulative or chunk-based text)
                                    delta = transcript
                                    if transcript.startswith(self._last_output_transcription):
                                        delta = transcript[len(self._last_output_transcription):]
                                    self._last_output_transcription = transcript
                                    
                                    # Only send if there's new text
                                    if delta:
                                        # Send to frontend (Streaming)
                                        self.emit("transcription", {"sender": "scarlett", "text": delta})
                                        
                                        # Buffer for Logging
                                        if self.chat_buffer["sender"] != "scarlett":
                                            # Flush previous
                                            if self.chat_buffer["sender"] and self.chat_buffer["text"].strip():
                                                self.project_manager.log_chat(self.chat_buffer["sender"], self.chat_buffer["text"])
                                            # Start new
                                            self.chat_buffer = {"sender": "scarlett", "text": delta}
                                        else:
                                            # Append
                                            self.chat_buffer["text"] += delta
                        
                        # Flush buffer on turn completion if needed, 
                        # but usually better to wait for sender switch or explicit end.
                        # We can also check turn_complete signal if available in response.server_content.model_turn etc

                    # 3. Handle Tool Calls
                    if response.tool_call:
                        print("The tool was called")
                        function_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[scarlett DEBUG] [TOOL] Detected tool call: '{fc.name}' with args: {fc.args}")
                            function_response = await self.tool_dispatcher.dispatch(fc)
                            if function_response is not None:
                                function_responses.append(function_response)
                        if function_responses:
                            await self.session.send_tool_response(function_responses=function_responses)
                
                # Turn/Response Loop Finished
                self.flush_chat()

                while not self.audio_in_queue.empty():
                    self.audio_in_queue.get_nowait()
        except Exception as e:
            print(f"Error in receive_audio: {e}")
            traceback.print_exc()
            # CRITICAL: Re-raise to crash the TaskGroup and trigger outer loop reconnect
            raise e

    async def run(self, start_message=None):
        retry_delay = 1
        is_reconnect = False
        
        while not self.stop_event.is_set():
            try:
                print(f"[scarlett DEBUG] [CONNECT] Connecting to Gemini Live API...")
                async with (
                    client.aio.live.connect(model=MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session = session

                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue = asyncio.Queue(maxsize=10)

                    tg.create_task(self.send_realtime())
                    tg.create_task(self.listen_audio())
                    # tg.create_task(self._process_video_queue()) # Removed in favor of VAD
                    
                    

                    if self.video_mode == "camera":
                        tg.create_task(self.get_frames())
                    elif self.video_mode == "screen":
                        tg.create_task(self.get_screen())

                    tg.create_task(self.receive_audio())
                    tg.create_task(self.play_audio())

                    # Handle Startup vs Reconnect Logic
                    if not is_reconnect:
                        if start_message:
                            print(f"[scarlett DEBUG] [INFO] Sending start message: {start_message}")
                            await self.session.send(input=start_message, end_of_turn=True)
                        
                        # Sync Project State
                        if self.project_manager:
                            self.emit("project_update", {"project": self.project_manager.current_project})
                    
                    else:
                        print(f"[scarlett DEBUG] [RECONNECT] Connection restored.")
                        # Restore Context
                        print(f"[scarlett DEBUG] [RECONNECT] Fetching recent chat history to restore context...")
                        history = self.project_manager.get_recent_chat_history(limit=10)
                        
                        context_msg = "System Notification: Connection was lost and just re-established. Here is the recent chat history to help you resume seamlessly:\n\n"
                        for entry in history:
                            sender = entry.get('sender', 'Unknown')
                            text = entry.get('text', '')
                            context_msg += f"[{sender}]: {text}\n"
                        
                        context_msg += "\nPlease acknowledge the reconnection to the user (e.g. 'I lost connection for a moment, but I'm back...') and resume what you were doing."
                        
                        print(f"[scarlett DEBUG] [RECONNECT] Sending restoration context to model...")
                        await self.session.send(input=context_msg, end_of_turn=True)

                    # Reset retry delay on successful connection
                    retry_delay = 1
                    
                    # Wait until stop event, or until the session task group exits (which happens on error)
                    # Actually, the TaskGroup context manager will exit if any tasks fail/cancel.
                    # We need to keep this block alive.
                    # The original code just waited on stop_event, but that doesn't account for session death.
                    # We should rely on the TaskGroup raising an exception when subtasks fail (like receive_audio).
                    
                    # However, since receive_audio is a task in the group, if it crashes (connection closed), 
                    # the group will cancel others and exit. We catch that exit below.
                    
                    # We can await stop_event, but if the connection dies, receive_audio crashes -> group closes -> we exit `async with` -> restart loop.
                    # To ensure we don't block indefinitely if connection dies silently (unlikely with receive_audio), we just wait.
                    await self.stop_event.wait()    

            except asyncio.CancelledError:
                print(f"[scarlett DEBUG] [STOP] Main loop cancelled.")
                break
                
            except Exception as e:
                # This catches the ExceptionGroup from TaskGroup or direct exceptions
                print(f"[scarlett DEBUG] [ERR] Connection Error: {e}")
                
                if self.stop_event.is_set():
                    break
                
                print(f"[scarlett DEBUG] [RETRY] Reconnecting in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 10) # Exponential backoff capped at 10s
                is_reconnect = True # Next loop will be a reconnect
                
            finally:
                # Cleanup before retry
                if hasattr(self, 'audio_stream') and self.audio_stream:
                    try:
                        self.audio_stream.close()
                    except: 
                        pass

def get_input_devices():
    p = pyaudio.PyAudio()
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    devices = []
    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
            devices.append((i, p.get_device_info_by_host_api_device_index(0, i).get('name')))
    p.terminate()
    return devices

def get_output_devices():
    p = pyaudio.PyAudio()
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    devices = []
    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(0, i).get('maxOutputChannels')) > 0:
            devices.append((i, p.get_device_info_by_host_api_device_index(0, i).get('name')))
    p.terminate()
    return devices

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        type=str,
        default=DEFAULT_MODE,
        help="pixels to stream from",
        choices=["camera", "screen", "none"],
    )
    args = parser.parse_args()
    main = AudioLoop(video_mode=args.mode)
    asyncio.run(main.run())