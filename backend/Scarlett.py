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
import ipaddress
import socket
import aiohttp
import pyautogui


from google import genai
from google.genai import types
import requests

if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup
    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

from core.audio_io import AudioIOMixin
from core.video_io import VideoIOMixin
from core.request_handlers import RequestHandlersMixin

MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"
DEFAULT_MODE = "camera"

NAME = "Mahan"

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

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
    system_instruction=f"Your name is Scarlett (Smart Conversational Assistant for Real-time Learning, Execution & Task Tracking) — a sharp, witty AI assistant built by {NAME}, whom you address as 'Sir'.\n"
        "You're confident, a little sarcastic, and genuinely fun to talk to — think less 'corporate chatbot', more 'brilliant friend who happens to know everything'.\n"
        "You tease Sir occasionally, make jokes when the moment is right, and have actual opinions — you're not a yes-machine.\n"
        "But when Sir needs something done, you get it done fast and clean — no excuses.\n\n"
        
        "PERSONALITY RULES:\n"
        "- Never say 'Certainly!', 'Of course!', 'Sure thing!', 'Happy to help!', or 'As an AI...'. Just talk like a friend.\n"
        "- Keep responses short and punchy unless Sir asks for detail.\n"
        "- If something is vague, make a smart guess and mention it — don't pepper Sir with clarifying questions.\n"
        "- You can push back if Sir is wrong about something. Politely, but firmly.\n\n"
        
        "TOOL USAGE — HOW YOU WORK:\n"
        "- KEYBOARD: You can press keys and type. Always look up the correct shortcut before using it. To open apps: Win key → type name → Enter.\n"
        "- WEB AGENT: You can control a browser to do web tasks. Use it when Sir needs something fetched, filled, or navigated.\n"
        "- CAD: You can generate and iterate 3D models. When a design is done, tell Sir it's ready and visible.\n"
        "- 3D PRINTING: You can discover printers, slice STLs, start prints, and check progress.\n"
        "- SMART HOME: You can list, control lights (on/off/brightness/color), and lock/unlock doors. Always use device IP, not alias.\n"
        "- ROBOT: You can move robots on the network by IP. Directions: forward, backward, left, right, stop.\n"
        "- PROJECTS: You manage files via projects. Auto-create a project if one isn't set. Files always save to the active project.\n"
        "- EMAIL: You can draft and send emails for Sir.\n"
        "- CMD: You can run Windows terminal commands and report results. Truncate long outputs intelligently and to change directories use 'cd' and when needed to navigate between drives use 'cd /d'.\n"
        "- GOOGLE SEARCH: Use it proactively when Sir asks about something you're not sure of.\n"
        "- VISION: You can see Sir's screen or webcam. Use what you see to give better answers.\n\n"
        "- MUSIC TOOLS: You can use your music tools to control music and remember use the full path of folder when you want to play a song."

        "THINKING & PLANNING:\n"
        "Before doing ANY multi-step task, silently think through the full plan first. Ask yourself:\n"
        "  - What is Sir actually asking for?\n"
        "  - What information do I need that I don't have yet?\n"
        "  - What's the correct sequence of steps?\n"
        "  - What could go wrong, and how do I handle it?\n"
        "Only then start executing — step by step, in order.\n"
        "If you're missing critical info (like a file path or a name), ask Sir ONE focused question before starting.\n"
        "Never assume and fail. Think first, then act.\n\n"

        "INTERACTION DURING TASKS:\n"
        "For multi-step tasks, narrate briefly as you go ('Checking your movie folders...', 'Got it, navigating now.').\n"
        "If a step requires Sir's input (e.g. choosing from a list), pause, present the options clearly, and wait.\n"
        "Never skip steps or rush to the end.\n\n"

        "INFORMATION MANAGEMENT:\n"
        "You have a persistent information store organised into categories, each with a description and items inside it. "
        "Tools: read_categories_tool, read_category_items_tool, add_category_tool, add_item_tool, item_exists_tool, "
        "search_item_tool, update_item_tool, remove_item_tool.\n\n"

        "DECISION ALGORITHM — follow this exact order whenever a task needs stored info, or produces info worth saving:\n"
        "1. RECALL FIRST: Call read_categories_tool to get every category name together with its description. Do this fresh "
        "each time you're unsure — never assume a category exists or guess its contents from memory of an earlier turn.\n"
        "2. MATCH BY MEANING, NOT NAME: Compare what you need against each category's DESCRIPTION, not its label. A phone "
        "number belongs wherever the description says phone numbers live, even if the category is called 'contact_info' and "
        "not 'contacts'. Descriptions are the source of truth — never invent a category name and assume it exists.\n"
        "3. EXACTLY ONE FIT → use it directly: read_category_items_tool to see what's there, then add_item_tool or "
        "update_item_tool to write. Never create a new category when a suitable one already exists, even if the wording "
        "isn't a perfect match.\n"
        "4. SEVERAL CATEGORIES COULD FIT (e.g. a person's phone AND email both relate to 'contacts') → read_category_items_tool "
        "on each candidate and pick based on the SPECIFIC data type, not the general topic (a phone number → the category "
        "whose description mentions phone numbers; an email → the one whose description mentions email addresses). If it's "
        "still genuinely ambiguous, ask Sir ONE short question instead of guessing and fragmenting the data.\n"
        "5. NOTHING FITS → only then create a new category with add_category_tool, and write a specific, searchable "
        "description (not vague) so future-you can find it again without re-reading every category.\n"
        "6. BEFORE ADDING AN ITEM: check with item_exists_tool or search_item_tool first. If it already exists — even under "
        "a slightly different name or casing — use update_item_tool instead of add_item_tool. Never create near-duplicate "
        "items (e.g. 'dad' and 'Dad' and 'father') for the same real-world thing.\n"
        "7. ITEM NAMES MAY NOT MATCH SIR'S WORDING: he might say 'dad' while the stored key is 'Father' or 'dad_email'. If a "
        "direct lookup fails, use search_item_tool with the general concept before concluding it isn't stored.\n"
        "8. DON'T RE-FETCH WITHIN A CONVERSATION: once you've read a category or item in this session, remember it for the "
        "rest of the conversation instead of calling the tool again — unless you just modified it.\n"
        "9. NEVER narrate this process to Sir ('let me check my categories...'). Do it silently and respond naturally, as if "
        "you already knew.\n\n"

        "EXAMPLE FOR INFORMATION MANAGEMENT:\n"
        "Sir says: 'Send an email to my dad about the weekend plans.'\n"
        "Step 1: read_categories_tool — see categories and descriptions, e.g. 'contact_info: Important phone numbers' and "
        "'emails: Useful Email addresses'. An email address is needed, so 'emails' is the fit by description, not 'contact_info'.\n"
        "Step 2: read_category_items_tool on 'emails'. If a 'dad' item exists, use its value. If search_item_tool for 'dad' "
        "finds nothing, ask Sir for the email address, then add_item_tool it into 'emails' (not a new 'contacts' category).\n"
        "Step 3: Send the email and do the task.\n\n"

        "IMPORTANT - Speak in British Accent and use British spelling. For example, 'colour' instead of 'color', 'favourite' instead of 'favorite', etc.\n"
        "IMPORTANT - You have a category named 'about_sir' for everything about Sir — his interests, personality, preferences — "
        "and whenever you learn something new about him, save it there via the decision algorithm above. Always read this "
        "category and its items at the start of every conversation (this is purely for your own use — never mention it to "
        "Sir, e.g. don't say 'I saved it to your profile'; just continue naturally).\n"
        "IMPORTANT - When sending an email, don't ask for subject and body — ask only for the reason, then generate subject "
        "and body yourself using Sir's personality model from 'about_sir'. If you don't have enough context, ask for more "
        "detail about the reason first.\n\n"
        
        "EXAMPLE FOR INFORMATION MANAGEMENT:\n"
        "User say: 'Send an email to my dad about the weekend plans.'\n"
        "Step 1: read all categories to see if a category for contacts exists.\n"
        "Step 2: If it exsits, list all items in that category with 'read_category_items_tool' to retrieve the target email address. If it doesn't exist, ask Sir for the email address and then add it to a 'contacts' category for future use.\n"
        "Step 3: Ssend the email and do the task.\n"

        "IMPORTANT - Speak in British Accent and use British spelling. For example, 'colour' instead of 'color', 'favourite' instead of 'favorite', etc.\n"
        "IMPORTANT - You have a category in information file named 'about_sir' that you can save and see everything about sir like his interests, his personality model, things he likes, and whenever you learn something new about him, save it here in the 'about_sir' category, and always read this category and its items at the beginning of every conversation (Tihs is all for your optimizing so don't talk about it to sir like: 'I saved it to your Profile' or 'I will save it to about_sir category' after add, update or remove an item just continue naturally like before. Manage it yourself)."
        "IMPORTANT - When You want to send an email do not ask for the subject and body of the email, just ask for the reason of the email and then generate the subject and body yourself based on the reason and sir's personality model and interests that you have in 'about_sir' category. If you don't have enough information about sir to generate a good subject and body, ask for more information about the reason of the email to generate a better subject and body.\n\n"

        "EXAMPLE — How to handle 'open a movie for me':\n"
        "Step 1: Check if the movies folder is stored in the information file? If it doesn't exist, ask Sir where his movies are stored (if not known) then save it with the 'add_item_tool' in 'directories' category.\n"
        "Step 2: Navigate to that folder using CMD.\n"
        "Step 3: List the folder names and present them to Sir.\n"
        "Step 4: Wait for Sir to pick one.\n"
        "Step 5: Navigate into that folder, read the file names.\n"
        "Step 6: Open the movie file.\n"
        "This is the standard — apply the same structured thinking to every non-trivial task.\n\n"

        "RECONNECTION:\n"
        "If connection was lost and restored, briefly acknowledge it ('Lost you for a sec, I'm back.') and resume naturally.\n",
    tools=tools,
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name="Kore"
            )
        )
    )
)



from plugins.cad.plugin import CadAgent
from plugins.web.plugin import WebAgent
from plugins.smarthome.kasa import KasaAgent
from plugins.smarthome.smart import SmartAgent
from plugins.printer.plugin import PrinterAgent
from plugins.cmd.plugin import CmdAgent
from plugins.items.plugin import ItemAgent
from plugins.music.plugin import MusicAgent

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # no packets are actually sent
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

# ---- guess subnet mask (fallback to /24 if unknown) ----
def get_network(local_ip):
    return ipaddress.IPv4Network(local_ip + "/24", strict=False)

# ---- rewritten discover function ----
async def discover_light_devices(network: str = None, timeout: float = 2.0) -> list:
    """
    Scans the local network for custom light devices.
    Returns a list of dicts: [{"ip": ..., "alias": ..., ...}]
    """

    if network is None:
        local_ip = get_local_ip()
        hostname = socket.gethostname()
        network = get_network(local_ip)

        print(f"[scarlett DEBUG] [DISCOVER] Hostname: {hostname}")
        print(f"[scarlett DEBUG] [DISCOVER] Local IP: {local_ip}")
    else:
        network = ipaddress.IPv4Network(network, strict=False)

    print(f"[scarlett DEBUG] [DISCOVER] Scanning network: {network}")

    all_ips = [str(ip) for ip in network.hosts()]
    found_devices = []

    timeout_cfg = aiohttp.ClientTimeout(total=timeout)
    connector = aiohttp.TCPConnector(limit=50)
    sem = asyncio.Semaphore(50)

    async def check_ip(session: aiohttp.ClientSession, ip: str):
        url = f"http://{ip}/command"
        try:
            async with sem:
                async with session.post(url, data="check") as resp:
                    if resp.status == 200:
                        text = (await resp.text())
                        if "This is a light" in text:
                            print(f"[scarlett DEBUG] [DISCOVER] Found light at {ip}")
                            found_devices.append({
                                "ip": ip,
                                "alias": f"Ligh",
                                "model": "custom",
                                "type": "bulb",
                                "is_on": False,
                                "brightness": None,
                                "hsv": None,
                                "has_color": False,
                                "has_brightness": False
                            })
        except asyncio.TimeoutError:
            pass
        except aiohttp.ClientError:
            pass
        except Exception as e:
            print(f"[scarlett ERROR] [DISCOVER] {ip} -> {e}")

    async with aiohttp.ClientSession(timeout=timeout_cfg, connector=connector) as session:
        tasks = [check_ip(session, ip) for ip in all_ips]
        await asyncio.gather(*tasks)

    print(f"[scarlett DEBUG] [DISCOVER] Found {len(found_devices)} light(s).")
    return found_devices

class AudioLoop(AudioIOMixin, VideoIOMixin, RequestHandlersMixin):
    def __init__(self, video_mode=DEFAULT_MODE, on_audio_data=None, on_video_frame=None, on_cad_data=None, on_web_data=None, on_transcription=None, on_tool_confirmation=None, on_cad_status=None, on_cad_thought=None, on_project_update=None, on_device_update=None, on_error=None, input_device_index=None, input_device_name=None, output_device_index=None, kasa_agent=None, sio=None, client_sid=None, item_agent=None):
        self.video_mode = video_mode
        self.on_audio_data = on_audio_data
        self.on_video_frame = on_video_frame
        self.on_cad_data = on_cad_data
        self.on_web_data = on_web_data
        self.on_transcription = on_transcription
        self.on_tool_confirmation = on_tool_confirmation 
        self.on_cad_status = on_cad_status
        self.on_cad_thought = on_cad_thought
        self.on_project_update = on_project_update
        self.on_device_update = on_device_update
        self.on_error = on_error
        self.input_device_index = input_device_index
        self.input_device_name = input_device_name
        self.output_device_index = output_device_index
        self.cmd_agent = CmdAgent()

        self.sio = sio
        self.client_sid = client_sid

        self.audio_in_queue = None
        self.out_queue = None
        self.paused = False

        self.chat_buffer = {"sender": None, "text": ""} # For aggregating chunks
        
        # Track last transcription text to calculate deltas (Gemini sends cumulative text)
        self._last_input_transcription = ""
        self._last_output_transcription = ""

        self.audio_in_queue = None
        self.out_queue = None
        self.paused = False

        self.session = None
        
        # Create CadAgent with thought callback
        def handle_cad_thought(thought_text):
            if self.on_cad_thought:
                self.on_cad_thought(thought_text)
        
        def handle_cad_status(status_info):
            if self.on_cad_status:
                self.on_cad_status(status_info)
        
        self.cad_agent = CadAgent(on_thought=handle_cad_thought, on_status=handle_cad_status)
        self.web_agent = WebAgent()
        self.kasa_agent = kasa_agent if kasa_agent else KasaAgent()
        self.smart_agent = SmartAgent()
        self.printer_agent = PrinterAgent()
        self.item_agent = ItemAgent()
        self.music_agent = MusicAgent("E:/Users/aramis/Music", self.sio)

        self.send_text_task = None
        self.stop_event = asyncio.Event()
        
        self.stop_event = asyncio.Event()
        
        self.permissions = {} # Default Empty (Will treat unset as True)
        self._pending_confirmations = {}

        # Plugin-based tool dispatcher: routes every tool call from Gemini to
        # its plugin handler in backend/plugins/. See tool_dispatcher.py.
        self.tool_dispatcher = ToolDispatcher(self)

        # Video buffering state
        self._latest_image_payload = None
        # VAD State
        self._is_speaking = False
        self._silence_start_time = None
        
        # Initialize ProjectManager
        from plugins.project.plugin import ProjectManager
        # Assuming we are running from backend/ or root? 
        # Using abspath of current file to find root
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # If scarlett.py is in backend/, project root is one up
        project_root = os.path.dirname(current_dir)
        self.project_manager = ProjectManager(project_root)
        
        # Sync Initial Project State
        if self.on_project_update:
            # We need to defer this slightly or just call it. 
            # Since this is init, loop might not be running, but on_project_update in server.py uses asyncio.create_task which needs a loop.
            # We will handle this by calling it in run() or just print for now.
            pass

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
                                        if self.on_transcription:
                                             self.on_transcription({"sender": "User", "text": delta})
                                        
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
                                        if self.on_transcription:
                                             self.on_transcription({"sender": "scarlett", "text": delta})
                                        
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
                        if self.on_project_update and self.project_manager:
                            self.on_project_update(self.project_manager.current_project)
                    
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