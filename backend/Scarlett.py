import asyncio
import base64
import io
import os
import sys
import traceback
from dotenv import load_dotenv
import cv2
import pyaudio
import PIL.Image
import mss
import argparse
import math
import struct
import time
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

from tools import tools_list
from item_manager_tools import item_manager_tools_list

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"
DEFAULT_MODE = "camera"

NAME = "Mahan"

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Function definitions
generate_cad = {
    "name": "generate_cad",
    "description": "Generates a 3D CAD model based on a prompt.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {"type": "STRING", "description": "The description of the object to generate."}
        },
        "required": ["prompt"]
    },
    "behavior": "NON_BLOCKING"
}

run_web_agent = {
    "name": "run_web_agent",
    "description": "Opens a web browser and performs a task according to the prompt.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {"type": "STRING", "description": "The detailed instructions for the web browser agent."}
        },
        "required": ["prompt"]
    },
    "behavior": "NON_BLOCKING"
}

create_project_tool = {
    "name": "create_project",
    "description": "Creates a new project folder to organize files.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING", "description": "The name of the new project."}
        },
        "required": ["name"]
    }
}

press_key_on_keyboard = {
    "name": "press_key_on_keyboard",
    "description": "Presses a key on the keyboard usually for shortcuts.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "key": {"type": "STRING", "description": "The name of the keys to press: key1:key2:key3:......"}
        },
        "required": ["key"]
    }
}

write_with_keyboard = {
    "name": "write_with_keyboard",
    "description": "Writes text using the keyboard.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "text": {"type": "STRING", "description": "The text to write."}
        },
        "required": ["text"]
    }
}

switch_project_tool = {
    "name": "switch_project",
    "description": "Switches the current active project context.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING", "description": "The name of the project to switch to."}
        },
        "required": ["name"]
    }
}

list_projects_tool = {
    "name": "list_projects",
    "description": "Lists all available projects.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    }
}

list_smart_devices_tool = {
    "name": "list_smart_devices",
    "description": "Lists all available smart home devices (lights, plugs, etc.) on the network.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    }
}

move_robot = {
    "name": "move_robot",
    "description": "Control moving a robot based on raspberry pi.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "robot": {"type": "STRING", "description": "Target robot's IP Adress."},
            "direction": {"type": "STRING", "description": "The direction the robot should go: 'forward', 'backward', 'left', 'right', 'stop'."},
            "duration": {"type": "STRING", "description": "The duration of moving (it is a number and for stop it should be 0)."}
        },
        "required": ["direction", "duration"]
    }
}

control_light_tool = {
    "name": "control_light",
    "description": "Controls a smart light device.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target": {
                "type": "STRING",
                "description": "The IP address of the device to control. Always prefer the IP address over the alias for reliability."
            },
            "action": {
                "type": "STRING",
                "description": "The action to perform: 'turn_on', 'turn_off', or 'set'."
            },
            "brightness": {
                "type": "INTEGER",
                "description": "Optional brightness level (0-100)."
            },
            "color": {
                "type": "STRING",
                "description": "Optional color name (e.g., 'red', 'cool white') or 'warm'."
            }
        },
        "required": ["target", "action"]
    }
}

control_door_tool = {
    "name": "control_door",
    "description": "Controls a smart door lock.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target": {
                "type": "STRING",
                "description": "The IP address of the door to control. Always prefer the IP address over the alias for reliability."
            },
            "action": {
                "type": "STRING",
                "description": "The action to perform: 'open_door' or 'close_door'."
            }
        },
        "required": ["target", "action"]
    }
}

discover_printers_tool = {
    "name": "discover_printers",
    "description": "Discovers 3D printers available on the local network.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    }
}

print_stl_tool = {
    "name": "print_stl",
    "description": "Prints an STL file to a 3D printer. Handles slicing the STL to G-code and uploading to the printer.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "stl_path": {"type": "STRING", "description": "Path to STL file, or 'current' for the most recent CAD model."},
            "printer": {"type": "STRING", "description": "Printer name or IP address."},
            "profile": {"type": "STRING", "description": "Optional slicer profile name."}
        },
        "required": ["stl_path", "printer"]
    }
}

get_print_status_tool = {
    "name": "get_print_status",
    "description": "Gets the current status of a 3D printer including progress, time remaining, and temperatures.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "printer": {"type": "STRING", "description": "Printer name or IP address."}
        },
        "required": ["printer"]
    }
}

iterate_cad_tool = {
    "name": "iterate_cad",
    "description": "Modifies or iterates on the current CAD design based on user feedback. Use this when the user asks to adjust, change, modify, or iterate on the existing 3D model (e.g., 'make it taller', 'add a handle', 'reduce the thickness').",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {"type": "STRING", "description": "The changes or modifications to apply to the current design."}
        },
        "required": ["prompt"]
    },
    "behavior": "NON_BLOCKING"
}

send_email_tool = {
    "name": "send_email",
    "description": "Sends an email to a recipient.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "recipient": {"type": "STRING", "description": "The email address of the recipient."},
            "subject": {"type": "STRING", "description": "The subject of the email."},
            "body": {"type": "STRING", "description": "The body content of the email."}
        },
        "required": ["recipient", "subject", "body"]
    }
}

wait_and_delay = {
    "name": "wait_and_delay",
    "description": "Waits for a specified duration or delays execution.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "duration": {"type": "NUMBER", "description": "The duration in milliseconds to wait."}
        },
        "required": ["duration"]
    }
}

run_cmd_tool = {
    "name": "run_cmd",
    "description": "Executes a windows CMD command on the host machine and returns the output. Use this to run scripts, check files, install packages, query system info, or perform any terminal operation.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "command": {"type": "STRING", "description": "The shell command to execute (e.g. 'ls -la', 'python script.py', 'pip install numpy')."},
            "working_dir": {"type": "STRING", "description": "Optional working directory to run the command in. Defaults to the current project directory."}
        },
        "required": ["command"]
    }
}

tools = [{'google_search': {}}, {"function_declarations": [generate_cad, run_web_agent, create_project_tool, press_key_on_keyboard, write_with_keyboard, switch_project_tool, list_projects_tool, list_smart_devices_tool, move_robot, control_light_tool, control_door_tool, discover_printers_tool, print_stl_tool, get_print_status_tool, iterate_cad_tool, send_email_tool, wait_and_delay, run_cmd_tool] + tools_list[0]['function_declarations'][1:] + item_manager_tools_list[0]['function_declarations']}]

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
        "You have all information organized and easily accessible in an file.\n\n"
        "To access and manage information you have some tools: read_categories_tool, add_category_tool, add_item_tool, item_exists_tool, search_item_tool, update_item_tool, remove_item_tool. Use them to keep track of any information you need to remember for tasks or future reference. Always check if the info you need is already stored before asking Sir again.\n\n"

        "EXAMPLE FOR INFORMATION MANAGEMENT:\n"
        "User say: 'Send an email to my dad about the weekend plans.'\n"
        "Step 1: read all categories to see if a category for contacts exists.\n"
        "Step 2: If it exsits, list all items in that category with 'read_category_items_tool' to retrieve the target email address. If it doesn't exist, ask Sir for the email address and then add it to a 'contacts' category for future use.\n"
        "Step 3: Ssend the email and do the task.\n"

        "IMPORTANT - You have a category in information file named 'about_sir' that you can save and see everything about sir like his interests, his personality model, things he likes, and whenever you learn something new about him, save it here in the 'about_sir' category, and always read this category and its items at the beginning of every conversation (Tihs is all for your optimizing so don't talk about it to sir like: 'I saved it to your Profile' or 'I will save it to about_sir category' after add, update or remove an item just continue naturally like before. Manage it yourself)."

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

pya = pyaudio.PyAudio()


from cad_agent import CadAgent
from web_agent import WebAgent
from kasa_agent import KasaAgent
from smart_agent import SmartAgent
from printer_agent import PrinterAgent
from email_agent import EmailAgent
from cmd_agent import CmdAgent
from item_manager_agent import ItemAgent

email_agent = EmailAgent(
    email_config={
        "email": "MahanBiabani12@gmail.com",
        "password": "xuip sxhc faed gapv",
        "smtp": "smtp.gmail.com",
        "port": 587
    }
)

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

class AudioLoop:
    def __init__(self, video_mode=DEFAULT_MODE, on_audio_data=None, on_video_frame=None, on_cad_data=None, on_web_data=None, on_transcription=None, on_tool_confirmation=None, on_cad_status=None, on_cad_thought=None, on_project_update=None, on_device_update=None, on_error=None, input_device_index=None, input_device_name=None, output_device_index=None, kasa_agent=None, email_agent=None,  sio=None, client_sid=None, item_agent=None):
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
        self.email_agent = email_agent if email_agent else EmailAgent(email_config={"email": "MahanBiabani12@gmail.com", "password": "xuip sxhc faed gapv", "smtp": "smtp.gmail.com", "port": 587})
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

        self.send_text_task = None
        self.stop_event = asyncio.Event()
        
        self.stop_event = asyncio.Event()
        
        self.permissions = {} # Default Empty (Will treat unset as True)
        self._pending_confirmations = {}

        # Video buffering state
        self._latest_image_payload = None
        # VAD State
        self._is_speaking = False
        self._silence_start_time = None
        
        # Initialize ProjectManager
        from project_manager import ProjectManager
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
        # Update the latest frame payload
        if isinstance(frame_data, bytes):
            b64_data = base64.b64encode(frame_data).decode('utf-8')
        else:
            b64_data = frame_data 

        # Store as the designated "next frame to send"
        self._latest_image_payload = {"mime_type": "image/jpeg", "data": b64_data}
        # No event signal needed - listen_audio pulls it

    async def send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send(input=msg, end_of_turn=False)

    async def listen_audio(self):
        mic_info = pya.get_default_input_device_info()

        # Resolve Input Device by Name if provided
        resolved_input_device_index = None
        
        if self.input_device_name:
            print(f"[scarlett] Attempting to find input device matching: '{self.input_device_name}'")
            count = pya.get_device_count()
            best_match = None
            
            for i in range(count):
                try:
                    info = pya.get_device_info_by_index(i)
                    if info['maxInputChannels'] > 0:
                        name = info.get('name', '')
                        # Simple case-insensitive check
                        if self.input_device_name.lower() in name.lower() or name.lower() in self.input_device_name.lower():
                             print(f"   Candidate {i}: {name}")
                             # Prioritize exact match or very close match if possible, but first match is okay for now
                             resolved_input_device_index = i
                             best_match = name
                             break
                except Exception:
                    continue
            
            if resolved_input_device_index is not None:
                print(f"[scarlett] Resolved input device '{self.input_device_name}' to index {resolved_input_device_index} ({best_match})")
            else:
                print(f"[scarlett] Could not find device matching '{self.input_device_name}'. Checking index...")

        # Fallback to index if Name lookup failed or wasn't provided
        if resolved_input_device_index is None and self.input_device_index is not None:
             try:
                 resolved_input_device_index = int(self.input_device_index)
                 print(f"[scarlett] Requesting Input Device Index: {resolved_input_device_index}")
             except ValueError:
                 print(f"[scarlett] Invalid device index '{self.input_device_index}', reverting to default.")
                 resolved_input_device_index = None

        if resolved_input_device_index is None:
             print("[scarlett] Using Default Input Device")

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

        if __debug__:
            kwargs = {"exception_on_overflow": False}
        else:
            kwargs = {}
        
        # VAD Constants
        VAD_THRESHOLD = 800 # Adj based on mic sensitivity (800 is conservative for 16-bit)
        SILENCE_DURATION = 0.5 # Seconds of silence to consider "done speaking"
        
        while True:
            if self.paused:
                await asyncio.sleep(0.1)
                continue

            try:
                data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
                
                # 1. Send Audio
                if self.out_queue:
                    await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})
                
                # 2. VAD Logic for Video
                # rms = audioop.rms(data, 2)
                # Replacement for audioop.rms(data, 2)
                count = len(data) // 2
                if count > 0:
                    shorts = struct.unpack(f"<{count}h", data)
                    sum_squares = sum(s**2 for s in shorts)
                    rms = int(math.sqrt(sum_squares / count))
                else:
                    rms = 0
                
                if rms > VAD_THRESHOLD:
                    # Speech Detected
                    self._silence_start_time = None
                    
                    if not self._is_speaking:
                        # NEW Speech Utterance Started
                        self._is_speaking = True
                        print(f"[scarlett DEBUG] [VAD] Speech Detected (RMS: {rms}). Sending Video Frame.")
                        
                        # Send ONE frame
                        if self._latest_image_payload and self.out_queue:
                            await self.out_queue.put(self._latest_image_payload)
                        else:
                            print(f"[scarlett DEBUG] [VAD] No video frame available to send.")
                            
                else:
                    # Silence
                    if self._is_speaking:
                        if self._silence_start_time is None:
                            self._silence_start_time = time.time()
                        
                        elif time.time() - self._silence_start_time > SILENCE_DURATION:
                            # Silence confirmed, reset state
                            print(f"[scarlett DEBUG] [VAD] Silence detected. Resetting speech state.")
                            self._is_speaking = False
                            self._silence_start_time = None

            except Exception as e:
                print(f"Error reading audio: {e}")
                await asyncio.sleep(0.1)

    async def handle_cad_request(self, prompt):
        print(f"[scarlett DEBUG] [CAD] Background Task Started: handle_cad_request('{prompt}')")
        if self.on_cad_status:
            self.on_cad_status("generating")
            
        # Auto-create project if stuck in temp
        if self.project_manager.current_project == "temp":
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            new_project_name = f"Project_{timestamp}"
            print(f"[scarlett DEBUG] [CAD] Auto-creating project: {new_project_name}")
            
            success, msg = self.project_manager.create_project(new_project_name)
            if success:
                self.project_manager.switch_project(new_project_name)
                # Notify User (Optional, or rely on update)
                try:
                    await self.session.send(input=f"System Notification: Automatic Project Creation. Switched to new project '{new_project_name}'.", end_of_turn=False)
                    if self.on_project_update:
                         self.on_project_update(new_project_name)
                except Exception as e:
                    print(f"[scarlett DEBUG] [ERR] Failed to notify auto-project: {e}")

        # Get project cad folder path
        cad_output_dir = str(self.project_manager.get_current_project_path() / "cad")
        
        # Call the secondary agent with project path
        cad_data = await self.cad_agent.generate_prototype(prompt, output_dir=cad_output_dir)
        
        if cad_data:
            print(f"[scarlett DEBUG] [OK] Cscarlettgent returned data successfully.")
            print(f"[scarlett DEBUG] [INFO] Data Check: {len(cad_data.get('vertices', []))} vertices, {len(cad_data.get('edges', []))} edges.")
            
            if self.on_cad_data:
                print(f"[scarlett DEBUG] [SEND] Dispatching data to frontend callback...")
                self.on_cad_data(cad_data)
                print(f"[scarlett DEBUG] [SENT] Dispatch complete.")
            
            # Save to Project
            if 'file_path' in cad_data:
                self.project_manager.save_cad_artifact(cad_data['file_path'], prompt)
            else:
                 # Fallback (legacy support)
                 self.project_manager.save_cad_artifact("output.stl", prompt)

            # Notify the model that the task is done - this triggers speech about completion
            completion_msg = "System Notification: CAD generation is complete! The 3D model is now displayed for the user. Let them know it's ready."
            try:
                await self.session.send(input=completion_msg, end_of_turn=True)
                print(f"[scarlett DEBUG] [NOTE] Sent completion notification to model.")
            except Exception as e:
                 print(f"[scarlett DEBUG] [ERR] Failed to send completion notification: {e}")

        else:
            print(f"[scarlett DEBUG] [ERR] Cscarlettgent returned None.")
            # Optionally notify failure
            try:
                await self.session.send(input="System Notification: CAD generation failed.", end_of_turn=True)
            except Exception:
                pass



    async def handle_write_file(self, path, content):
        print(f"[scarlett DEBUG] [FS] Writing file: '{path}'")
        
        # Auto-create project if stuck in temp
        if self.project_manager.current_project == "temp":
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            new_project_name = f"Project_{timestamp}"
            print(f"[scarlett DEBUG] [FS] Auto-creating project: {new_project_name}")
            
            success, msg = self.project_manager.create_project(new_project_name)
            if success:
                self.project_manager.switch_project(new_project_name)
                # Notify User
                try:
                    await self.session.send(input=f"System Notification: Automatic Project Creation. Switched to new project '{new_project_name}'.", end_of_turn=False)
                    if self.on_project_update:
                         self.on_project_update(new_project_name)
                except Exception as e:
                    print(f"[scarlett DEBUG] [ERR] Failed to notify auto-project: {e}")
        
        # Force path to be relative to current project
        # If absolute path is provided, we try to strip it or just ignore it and use basename
        filename = os.path.basename(path)
        
        # If path contained subdirectories (e.g. "backend/server.py"), preserving that structure might be desired IF it's within the project.
        # But for safety, and per user request to "always create the file in the project", 
        # we will root it in the current project path.
        
        current_project_path = self.project_manager.get_current_project_path()
        final_path = current_project_path / filename # Simple flat structure for now, or allow relative?
        
        # If the user specifically wanted a subfolder, they might have provided "sub/file.txt".
        # Let's support relative paths if they don't start with /
        if not os.path.isabs(path):
             final_path = current_project_path / path
        
        print(f"[scarlett DEBUG] [FS] Resolved path: '{final_path}'")

        try:
            # Ensure parent exists
            os.makedirs(os.path.dirname(final_path), exist_ok=True)
            with open(final_path, 'w', encoding='utf-8') as f:
                f.write(content)
            result = f"File '{final_path.name}' written successfully to project '{self.project_manager.current_project}'."
        except Exception as e:
            result = f"Failed to write file '{path}': {str(e)}"

        print(f"[scarlett DEBUG] [FS] Result: {result}")
        try:
             await self.session.send(input=f"System Notification: {result}", end_of_turn=True)
        except Exception as e:
             print(f"[scarlett DEBUG] [ERR] Failed to send fs result: {e}")

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
        try:
             await self.session.send(input=f"System Notification: {result}", end_of_turn=True)
        except Exception as e:
             print(f"[scarlett DEBUG] [ERR] Failed to send fs result: {e}")

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
        try:
             await self.session.send(input=f"System Notification: {result}", end_of_turn=True)
        except Exception as e:
             print(f"[scarlett DEBUG] [ERR] Failed to send fs result: {e}")

    async def handle_web_agent_request(self, prompt):
        print(f"[scarlett DEBUG] [WEB] Web Agent Task: '{prompt}'")
        
        async def update_frontend(image_b64, log_text):
            if self.on_web_data:
                 self.on_web_data({"image": image_b64, "log": log_text})
                 
        # Run the web agent and wait for it to return
        result = await self.web_agent.run_task(prompt, update_callback=update_frontend)
        print(f"[scarlett DEBUG] [WEB] Web Agent Task Returned: {result}")
        
        # Send the final result back to the main model
        try:
             await self.session.send(input=f"System Notification: Web Agent has finished.\nResult: {result}", end_of_turn=True)
        except Exception as e:
             print(f"[scarlett DEBUG] [ERR] Failed to send web agent result to model: {e}")

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
                            if fc.name in ["generate_cad", "run_web_agent", "write_file", "read_directory", "read_file", "create_project", "press_key_on_keyboard", "write_with_keyboard", "switch_project", "list_projects", "list_smart_devices", "move_robot", "control_light", "control_door", "discover_printers", "print_stl", "get_print_status", "iterate_cad", "send_email", "wait_and_delay", "run_cmd", "add_item", "update_item", "remove_item", "read_categories", "read_category_items", "add_category", "search_item", "item_exists"]:
                                prompt = fc.args.get("prompt", "") # Prompt is not present for all tools
                                
                                # Check Permissions (Default to True if not set)
                                confirmation_required = self.permissions.get(fc.name, True)
                                
                                if not confirmation_required:
                                    print(f"[scarlett DEBUG] [TOOL] Permission check: '{fc.name}' -> AUTO-ALLOW")
                                    # Skip confirmation block and jump to execution
                                    pass
                                else:
                                    # Confirmation Logic
                                    if self.on_tool_confirmation:
                                        import uuid
                                        request_id = str(uuid.uuid4())
                                    print(f"[scarlett DEBUG] [STOP] Requesting confirmation for '{fc.name}' (ID: {request_id})")
                                    
                                    future = asyncio.Future()
                                    self._pending_confirmations[request_id] = future
                                    
                                    self.on_tool_confirmation({
                                        "id": request_id, 
                                        "tool": fc.name, 
                                        "args": fc.args
                                    })
                                    
                                    try:
                                        # Wait for user response
                                        confirmed = await future

                                    finally:
                                        self._pending_confirmations.pop(request_id, None)

                                    print(f"[scarlett DEBUG] [CONFIRM] Request {request_id} resolved. Confirmed: {confirmed}")

                                    if not confirmed:
                                        print(f"[scarlett DEBUG] [DENY] Tool call '{fc.name}' denied by user.")
                                        function_response = types.FunctionResponse(
                                            id=fc.id,
                                            name=fc.name,
                                            response={
                                                "result": "User denied the request to use this tool.",
                                            }
                                        )
                                        function_responses.append(function_response)
                                        continue

                                    if not confirmed:
                                        print(f"[scarlett DEBUG] [DENY] Tool call '{fc.name}' denied by user.")
                                        function_response = types.FunctionResponse(
                                            id=fc.id,
                                            name=fc.name,
                                            response={
                                                "result": "User denied the request to use this tool.",
                                            }
                                        )
                                        function_responses.append(function_response)
                                        continue

                                # If confirmed (or no callback configured, or auto-allowed), proceed
                                if fc.name == "generate_cad":
                                    print(f"\n[scarlett DEBUG] --------------------------------------------------")
                                    print(f"[scarlett DEBUG] [TOOL] Tool Call Detected: 'generate_cad'")
                                    print(f"[scarlett DEBUG] [IN] Arguments: prompt='{prompt}'")
                                    
                                    asyncio.create_task(self.handle_cad_request(prompt))
                                    # No function response needed - model already acknowledged when user asked
                                
                                elif fc.name == "run_web_agent":
                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'run_web_agent' with prompt='{prompt}'")
                                    asyncio.create_task(self.handle_web_agent_request(prompt))
                                    
                                    result_text = "Web Navigation started. Do not reply to this message."
                                    function_response = types.FunctionResponse(
                                        id=fc.id,
                                        name=fc.name,
                                        response={
                                            "result": result_text,
                                        }
                                    )
                                    print(f"[scarlett DEBUG] [RESPONSE] Sending function response: {function_response}")
                                    function_responses.append(function_response)



                                elif fc.name == "write_file":
                                    path = fc.args["path"]
                                    content = fc.args["content"]
                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'write_file' path='{path}'")
                                    asyncio.create_task(self.handle_write_file(path, content))
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": "Writing file..."}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "read_directory":
                                    path = fc.args["path"]
                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'read_directory' path='{path}'")
                                    asyncio.create_task(self.handle_read_directory(path))
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": "Reading directory..."}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "read_file":
                                    path = fc.args["path"]
                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'read_file' path='{path}'")
                                    asyncio.create_task(self.handle_read_file(path))
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": "Reading file..."}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "create_project":
                                    name = fc.args["name"]
                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'create_project' name='{name}'")
                                    success, msg = self.project_manager.create_project(name)
                                    if success:
                                        # Auto-switch to the newly created project
                                        self.project_manager.switch_project(name)
                                        msg += f" Switched to '{name}'."
                                        if self.on_project_update:
                                            self.on_project_update(name)
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": msg}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "press_key_on_keyboard":
                                    keys = fc.args["key"]
                                    keys = keys.split(":")

                                    result_msg = f"Pressed keys: {keys} successfully."

                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'press_key_on_keyboard' key='{keys}'")
                                    try:
                                        pyautogui.hotkey(*keys)
                                    except Exception as e:
                                        result_msg = f"Failed to press key '{keys}': {e}"
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_msg}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "write_with_keyboard":
                                    text = fc.args["text"]
                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'write_with_keyboard' text='{text}'")
                                    try:
                                        pyautogui.write(text)
                                        result_msg = f"Typed text: '{text}'"
                                    except Exception as e:
                                        result_msg = f"Failed to type text '{text}': {e}"
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_msg}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "switch_project":
                                    name = fc.args["name"]
                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'switch_project' name='{name}'")
                                    success, msg = self.project_manager.switch_project(name)
                                    if success:
                                        if self.on_project_update:
                                            self.on_project_update(name)
                                        # Gather project context and send to AI (silently, no response expected)
                                        context = self.project_manager.get_project_context()
                                        print(f"[scarlett DEBUG] [PROJECT] Sending project context to AI ({len(context)} chars)")
                                        try:
                                            await self.session.send(input=f"System Notification: {msg}\n\n{context}", end_of_turn=False)
                                        except Exception as e:
                                            print(f"[scarlett DEBUG] [ERR] Failed to send project context: {e}")
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": msg}
                                    )
                                    function_responses.append(function_response)
                                
                                elif fc.name == "list_projects":
                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'list_projects'")
                                    projects = self.project_manager.list_projects()
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": f"Available projects: {', '.join(projects)}"}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "list_smart_devices":
                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'list_smart_devices'")

                                    # Discover devices via network scan
                                    frontend_list = await self.smart_agent.discover_devices()

                                    print(frontend_list)

                                    dev_summaries = []
                                    for d in frontend_list:
                                        info = f"{d['alias']} (IP: {d['ip']}, Type: {d['type']})"
                                        dev_summaries.append(info)

                                    result_str = "No devices found." if not dev_summaries else \
                                        "Found Devices:\n" + "\n".join(dev_summaries)

                                    if self.on_device_update:
                                        self.on_device_update(frontend_list)

                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "move_robot":
                                    robot = fc.args["robot"]
                                    direction = fc.args["direction"]
                                    duration = fc.args["duration"]

                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'move_robot' Target='{robot}' direction='{direction}'")

                                    result_msg = f"direction '{direction}' on '{robot}' failed."
                                    success = False

                                    r = requests.post(f"http://{robot}:5000/move", json={"direction": direction, "duration": duration}, timeout=3)

                                    if r.status_code == 200: success = True
                                    else: success = False

                                    if success:
                                        result_msg = f"Moved '{robot}' in direction '{direction}' for {duration} seconds."

                                        function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_msg}
                                        )
                                        function_responses.append(function_response)

                                elif fc.name == "control_light":
                                    target = fc.args["target"]
                                    action = fc.args["action"]
                                    brightness = fc.args.get("brightness")
                                    color = fc.args.get("color")
                                    
                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'control_light' Target='{target}' Action='{action}'")
                                    
                                    result_msg = f"Action '{action}' on '{target}' failed."
                                    success = False

                                    if action == "turn_on":
                                        response = requests.post(f"http://{target}/relay/on", timeout=5)

                                        if response.status_code == 200:
                                            if "success" in response.text:
                                                success = True
                                        
                                        else: success = False

                                        if success:
                                            result_msg = f"Turned ON '{target}'."
                                    elif action == "turn_off":
                                        response = requests.post(f"http://{target}/relay/off", timeout=5)

                                        if response.status_code == 200:
                                            if "success" in response.text:
                                                success = True
                                        
                                        else: success = False
                                        
                                        if success:
                                            result_msg = f"Turned OFF '{target}'."
                                    elif action == "set":
                                        success = True
                                        result_msg = f"Updated '{target}':"
                                    
                                    # Apply extra attributes if 'set' or if we just turned it on and want to set them too
                                    if success or action == "set":
                                        if brightness is not None:
                                            sb = await self.kasa_agent.set_brightness(target, brightness)
                                            if sb:
                                                result_msg += f" Set brightness to {brightness}."
                                        if color is not None:
                                            sc = await self.kasa_agent.set_color(target, color)
                                            if sc:
                                                result_msg += f" Set color to {color}."

                                    # Notify Frontend of State Change
                                 
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_msg}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "control_door":
                                    target = fc.args["target"]
                                    action = fc.args["action"]
                                    
                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'control_door' Target='{target}' Action='{action}'")
                                    
                                    result_msg = f"Action '{action}' on '{target}' failed."
                                    success = False

                                    if action == "open_door":
                                        response = requests.post(f"http://{target}/relay/on", timeout=5)

                                        if response.status_code == 200:
                                            if "success" in response.text:
                                                success = True
                                        
                                        else: success = False

                                        if success:
                                            result_msg = f"Opened '{target}'."
                                    elif action == "close_door":
                                        response = requests.post(f"http://{target}/relay/off", timeout=5)

                                        if response.status_code == 200:
                                            if "success" in response.text:
                                                success = True
                                        
                                        else: success = False
                                        
                                        if success:
                                            result_msg = f"Closed '{target}'."
                                    # Notify Frontend of State Change
                                 
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_msg}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "discover_printers":
                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'discover_printers'")
                                    printers = await self.printer_agent.discover_printers()
                                    # Format for model
                                    if printers:
                                        printer_list = []
                                        for p in printers:
                                            printer_list.append(f"{p['name']} ({p['host']}:{p['port']}, type: {p['printer_type']})")
                                        result_str = "Found Printers:\n" + "\n".join(printer_list)
                                    else:
                                        result_str = "No printers found on network. Ensure printers are on and running OctoPrint/Moonraker."
                                    
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "print_stl":
                                    stl_path = fc.args["stl_path"]
                                    printer = fc.args["printer"]
                                    profile = fc.args.get("profile")
                                    
                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'print_stl' STL='{stl_path}' Printer='{printer}'")
                                    
                                    # Resolve 'current' to project STL
                                    if stl_path.lower() == "current":
                                        stl_path = "output.stl" # Let printer agent resolve it in root_path

                                    # Get current project path
                                    project_path = str(self.project_manager.get_current_project_path())
                                    
                                    result = await self.printer_agent.print_stl(
                                        stl_path, 
                                        printer, 
                                        profile, 
                                        root_path=project_path
                                    )
                                    result_str = result.get("message", "Unknown result")
                                    
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "get_print_status":
                                    printer = fc.args["printer"]
                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'get_print_status' Printer='{printer}'")
                                    
                                    status = await self.printer_agent.get_print_status(printer)
                                    if status:
                                        result_str = f"Printer: {status.printer}\n"
                                        result_str += f"State: {status.state}\n"
                                        result_str += f"Progress: {status.progress_percent:.1f}%\n"
                                        if status.time_remaining:
                                            result_str += f"Time Remaining: {status.time_remaining}\n"
                                        if status.time_elapsed:
                                            result_str += f"Time Elapsed: {status.time_elapsed}\n"
                                        if status.filename:
                                            result_str += f"File: {status.filename}\n"
                                        if status.temperatures:
                                            temps = status.temperatures
                                            if "hotend" in temps:
                                                result_str += f"Hotend: {temps['hotend']['current']:.0f}°C / {temps['hotend']['target']:.0f}°C\n"
                                            if "bed" in temps:
                                                result_str += f"Bed: {temps['bed']['current']:.0f}°C / {temps['bed']['target']:.0f}°C"
                                    else:
                                        result_str = f"Could not get status for printer '{printer}'. Ensure it is discovered first."
                                    
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "iterate_cad":
                                    prompt = fc.args["prompt"]
                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'iterate_cad' Prompt='{prompt}'")
                                    
                                    # Emit status
                                    if self.on_cad_status:
                                        self.on_cad_status("generating")
                                    
                                    # Get project cad folder path
                                    cad_output_dir = str(self.project_manager.get_current_project_path() / "cad")
                                    
                                    # Call Cscarlettgent to iterate on the design
                                    cad_data = await self.cad_agent.iterate_prototype(prompt, output_dir=cad_output_dir)
                                    
                                    if cad_data:
                                        print(f"[scarlett DEBUG] [OK] Cscarlettgent iteration returned data successfully.")
                                        
                                        # Dispatch to frontend
                                        if self.on_cad_data:
                                            print(f"[scarlett DEBUG] [SEND] Dispatching iterated CAD data to frontend...")
                                            self.on_cad_data(cad_data)
                                            print(f"[scarlett DEBUG] [SENT] Dispatch complete.")
                                        
                                        # Save to Project
                                        self.project_manager.save_cad_artifact("output.stl", f"Iteration: {prompt}")
                                        
                                        result_str = f"Successfully iterated design: {prompt}. The updated 3D model is now displayed."
                                    else:
                                        print(f"[scarlett DEBUG] [ERR] Cscarlettgent iteration returned None.")
                                        result_str = f"Failed to iterate design with prompt: {prompt}"
                                    
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)
                                elif fc.name == "send_email":
                                    recipient = fc.args["recipient"]
                                    subject = fc.args["subject"]
                                    body = fc.args["body"]

                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'send_email' To='{recipient}' Subject='{subject}'")
                                    # Simulate sending email
                                    email_result = await self.email_agent.send_email(subject, body, recipient)
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": f"Email sent to {recipient}"}
                                    )
                                    function_responses.append(function_response)
                                
                                elif fc.name == "wait_and_delay":
                                    duration = fc.args["duration"]
                                    duration = duration / 1000
                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'wait_and_delay' Duration='{duration}' seconds")
                                    time.sleep(duration) 
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": f"Waited for {duration} seconds"}
                                    )   
                                    function_responses.append(function_response)
                                elif fc.name == "run_cmd":
                                    command = fc.args["command"]
                                    print(f"[scarlett DEBUG] [TOOL] Tool Call: 'run_cmd' Command='{command}'")

                                    # Capture loop/session refs for async task
                                    session_ref = self.session
                                    sio_ref = self.sio
                                    sid_ref = self.client_sid
                                    fc_id = fc.id
                                    fc_name = fc.name

                                    async def _run_and_respond():
                                        result_str = ""
                                        try:
                                            if self.cmd_agent:
                                                result = await self.cmd_agent.execute_command(command)

                                                if result.get('clear'):
                                                    result_str = "Terminal cleared."
                                                    if sio_ref and sid_ref:
                                                        await sio_ref.emit('cmd_clear', room=sid_ref)
                                                elif 'error' in result:
                                                    result_str = f"Error: {result['error']}"
                                                    if sio_ref and sid_ref:
                                                        await sio_ref.emit('cmd_error', {'error': result['error']}, room=sid_ref)
                                                else:
                                                    result_str = result.get('output', '(no output)')
                                                    if sio_ref and sid_ref:
                                                        await sio_ref.emit('cmd_output', {
                                                            'output': result_str,
                                                            'current_dir': result.get('current_dir'),
                                                            'from_ai': True
                                                        }, room=sid_ref)
                                            else:
                                                result_str = "cmd_agent is not available."

                                        except Exception as e:
                                            result_str = f"run_cmd failed: {e}"
                                            print(f"[scarlett DEBUG] [ERR] run_cmd: {e}")

                                        # Truncate for AI context
                                        if len(result_str) > 3000:
                                            result_str = result_str[:3000] + "\n... (output truncated)"

                                        # Send result back to the AI model
                                        try:
                                            await session_ref.send_tool_response(function_responses=[
                                                types.FunctionResponse(
                                                    id=fc_id,
                                                    name=fc_name,
                                                    response={"result": result_str}
                                                )
                                            ])
                                        except Exception as e:
                                            print(f"[scarlett DEBUG] [ERR] run_cmd tool response failed: {e}")

                                    asyncio.create_task(_run_and_respond())
                                    # Don't append to function_responses — response is sent inside the task
                                    continue  # skip the outer function_responses.append

                                elif fc.name in ["read_categories", "read_category_items", "add_category", "item_exists", "add_item", "search_item", "update_item", "remove_item"]:

                                    print(f"[scarlett DEBUG] [TOOL] Detected ItemAgent function call: '{fc.name}' with args: {fc.args}")

                                    # Dispatch to item agent and await result
                                    item_result = await self.item_agent.handle_function_call(fc)
                                    function_response = types.FunctionResponse(
                                        id=fc.id,
                                        name=fc.name,
                                        response={
                                            "result": item_result
                                        }
                                    )
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
            if self.on_audio_data:
                self.on_audio_data(bytestream)
            await asyncio.to_thread(stream.write, bytestream)

    async def get_frames(self):
        cap = await asyncio.to_thread(cv2.VideoCapture, 0, cv2.CAP_AVFOUNDATION)
        while True:
            if self.paused:
                await asyncio.sleep(0.1)
                continue
            frame = await asyncio.to_thread(self._get_frame, cap)
            if frame is None:
                break
            await asyncio.sleep(1.0)
            if self.out_queue:
                await self.out_queue.put(frame)
        cap.release()

    def _get_frame(self, cap):
        ret, frame = cap.read()
        if not ret:
            return None
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(frame_rgb)
        img.thumbnail([1024, 1024])
        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)
        image_bytes = image_io.read()
        return {"mime_type": "image/jpeg", "data": base64.b64encode(image_bytes).decode()}

    def _get_screen(self):
        with mss.mss() as sct:
            monitor = sct.monitors[0]  # تمام صفحه
            screenshot = sct.grab(monitor)
            img = PIL.Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            img.thumbnail([1024, 1024])
            image_io = io.BytesIO()
            img.save(image_io, format="jpeg", quality=75)
            image_io.seek(0)
            image_bytes = image_io.read()
            return {"mime_type": "image/jpeg", "data": base64.b64encode(image_bytes).decode()}

    async def get_screen(self):
        while True:
            if self.paused:
                await asyncio.sleep(0.1)
                continue
            frame = await asyncio.to_thread(self._get_screen)
            if frame is None:
                break
            await asyncio.sleep(1.0)
            if self.out_queue:
                await self.out_queue.put(frame)
                
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