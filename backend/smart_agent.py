import asyncio
import ipaddress
import socket
import aiohttp
import json
from kasa import Discover, SmartDevice, SmartBulb, SmartPlug

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

class SmartAgent:
    def __init__(self, known_devices=None):
        self.devices = {}
        self.known_devices_config = known_devices or []

    async def initialize(self):
        """Initializes devices from the saved configuration."""
        if self.known_devices_config:
            print(f"[KasaAgent] Initializing {len(self.known_devices_config)} known devices...")
            tasks = []
            for d in self.known_devices_config:
                if not d: continue
                ip = d.get('ip')
                alias = d.get('alias')
                if ip:
                    # Create a device instance from IP
                    tasks.append(self._add_known_device(ip, alias, d))
            
            if tasks:
                await asyncio.gather(*tasks)

    async def _add_known_device(self, ip, alias, info):
        """Adds a device from settings without discovery scan."""
        try:
            # We can't know the exact class (Bulb/Plug) without connecting, 
            # but Discover.discover_single might work, or just SmartDevice(ip)
            # SmartDevice is the base class.
            dev = await Discover.discover_single(ip)
            if dev:
                await dev.update()
                self.devices[ip] = dev
                print(f"[KasaAgent] Loaded known device: {dev.alias} ({ip})")
            else:
                 print(f"[KasaAgent] Could not connect to known device at {ip}")
        except Exception as e:
            print(f"[KasaAgent] Error loading known device {ip}: {e}")


    # ---- rewritten discover function ----
    async def discover_devices(self, network: str = None, timeout: float = 2.0) -> list:
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
            print(network)
            # network = ipaddress.IPv4Network(network, strict=False)

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
                            print(f"[scarlett RAW] {ip} -> {repr(text)}")
                            text = json.loads(text)
                            print(f"[scarlett DEBUG] [DISCOVER] Device Type: {text['device']}")
                            
                            if text['message'] == "A smart device":
                                print(f"[scarlett DEBUG] [DISCOVER] Found device at {ip}")
                                found_devices.append({
                                    "ip": ip,
                                    "alias": text['place'],
                                    "model": "custom",
                                    "type": text['device'],
                                    "is_on": False,
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

        print(f"[scarlett DEBUG] [DISCOVER] Found {len(found_devices)} device(s).")
        return found_devices
    
    def get_device_by_type(self, devices, target_type):
        """" Finds a device by its type"""
        output_list = []
        for dev in devices:
            print(f"[scarlett DEBUG] [TYPE] Device: {dev['type'].lower()}")
            if dev['type'].lower() == target_type.lower():
                output_list.append(dev)
        return output_list

    def get_device_by_alias(self, alias):
        """Finds a device by its alias (case-insensitive)."""
        for ip, dev in self.devices.items():
            if dev.alias.lower() == alias.lower():
                return dev
        return None

    def _resolve_device(self, target):
        """Resolves a target string (IP or Alias) to a device object."""
        # check if it is an IP 
        if target in self.devices:
            return self.devices[target]
        
        # Check alias
        dev = self.get_device_by_alias(target)
        if dev:
            return dev
            
        return None

    def name_to_hsv(self, color_name):
        """Converts common color names to HSV (Hue, Saturation, Value).
           Hue: 0-360, Sat: 0-100, Val: 0-100
        """
        color_name = color_name.lower().strip()
        colors = {
            "red": (0, 100, 100),
            "orange": (30, 100, 100),
            "yellow": (60, 100, 100),
            "green": (120, 100, 100),
            "cyan": (180, 100, 100),
            "blue": (240, 100, 100),
            "purple": (300, 100, 100),
            "pink": (300, 50, 100),
            "white": (0, 0, 100),
            "warm": (30, 20, 100), # Warm White approx
            "cool": (200, 10, 100), # Cool White approx
            "daylight": (0, 0, 100),
        }
        return colors.get(color_name, None)

    async def turn_on(self, target):
        """Turns on the device (Target: IP or Alias)."""
        dev = self._resolve_device(target)
        if dev:
            try:
                await dev.turn_on()
                await dev.update()
                return True
            except Exception as e:
                print(f"Error turning on {target}: {e}")
                return False
        
        # Fallback: Try to discover single if it looks like an IP
        if target.count(".") == 3:
             try:
                dev = await Discover.discover_single(target)
                if dev:
                    self.devices[target] = dev
                    await dev.turn_on()
                    await dev.update()
                    return True
             except Exception:
                 pass
        return False

    async def turn_off(self, target):
        """Turns off the device (Target: IP or Alias)."""
        dev = self._resolve_device(target)
        if dev:
            try:
                await dev.turn_off()
                await dev.update()
                return True
            except Exception as e:
                print(f"Error turning off {target}: {e}")
                return False
        
        if target.count(".") == 3:
             try:
                dev = await Discover.discover_single(target)
                if dev:
                    self.devices[target] = dev
                    await dev.turn_off()
                    await dev.update()
                    return True
             except Exception:
                 pass
        return False

    async def set_brightness(self, target, brightness):
        """Sets brightness (0-100)."""
        dev = self._resolve_device(target)
        if dev and (dev.is_dimmable or dev.is_bulb):
            try:
                await dev.set_brightness(int(brightness))
                await dev.update()
                return True
            except Exception as e:
                 print(f"Error setting brightness for {target}: {e}")
        return False

    async def set_color(self, target, color_input):
        """Sets color by name or direct HSV tuple."""
        dev = self._resolve_device(target)
        if not dev or not dev.is_color:
            return False

        hsv = None
        if isinstance(color_input, str):
            hsv = self.name_to_hsv(color_input)
        elif isinstance(color_input, (tuple, list)) and len(color_input) == 3:
            hsv = color_input
        
        if hsv:
            try:
                # Kasa expects Hue (0-360), Sat (0-100), Val (0-100)
                await dev.set_hsv(int(hsv[0]), int(hsv[1]), int(hsv[2]))
                await dev.update()
                return True
            except Exception as e:
                 print(f"Error setting color for {target}: {e}")
        return False

# Standalone test
if __name__ == "__main__":
    async def main():
        agent = SmartAgent()
        await agent.discover_devices()
        print("Devices:", agent.devices)
        
        # Example Test
        # await agent.turn_on("Bedroom Light")
        # await agent.set_color("Bedroom Light", "Red")
    
    asyncio.run(main())
