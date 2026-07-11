import asyncio
import json
import threading
import time
import queue
import requests
import websockets

DEBUG = False

def debug_print(message, category="REMOTE"):
    if DEBUG:
        print(f"[{category}] {message}")

class RemoteShowdownWrapper:
    def __init__(self, username, password, formatid="gen9randombattle"):
        self.username = username
        self.password = password
        self.formatid = formatid
        self.ws_url = "wss://sim3.psim.us/showdown/websocket"
        
        self.q = queue.Queue()
        self.ws = None
        self.loop = asyncio.new_event_loop()
        self.current_room = ""
        self.bot_side = None # "p1" or "p2"
        self.logged_in = False
        self.in_battle = False  # True once we're inside a battle room
        
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
        start = time.time()
        while not self.ws and time.time() - start < 10:
            time.sleep(0.1)
            
        if not self.ws:
            raise Exception("Failed to connect to Showdown WebSocket within timeout")

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._connect_and_listen())

    async def _connect_and_listen(self):
        self._closed = False
        while not getattr(self, '_closed', False):
            try:
                async with websockets.connect(self.ws_url, ping_interval=None) as ws:
                    self.ws = ws
                    # Reset per-connection state
                    self.logged_in = False
                    debug_print("Connected to WebSocket", "REMOTE")
                    try:
                        async for message in ws:
                            debug_print(f"Received: {message}", "REMOTE")
                            lines = message.split('\n')
                            
                            # Track current room
                            if lines[0].startswith(">battle-"):
                                room = lines[0][1:]
                                if room != self.current_room:
                                    self.current_room = room
                                    self.in_battle = True
                                    debug_print(f"In battle room: {room}", "REMOTE")
                            
                            for line in lines:
                                if line.startswith("|challstr|"):
                                    challstr = line[10:]
                                    self._login(challstr)
                                    
                                # Detect which side we are
                                if line.startswith("|player|"):
                                    parts = line.split("|")
                                    if len(parts) >= 4:
                                        side = parts[2]
                                        name = parts[3]
                                        if name.lower() == self.username.lower():
                                            self.bot_side = side
                                            debug_print(f"We are {self.bot_side}", "REMOTE")

                                # Handle |updateuser| to know when login succeeded
                                if line.startswith("|updateuser|"):
                                    parts = line.split("|")
                                    if len(parts) >= 3 and parts[2].strip().lower() == self.username.lower():
                                        self.logged_in = True

                                # Battle ended – reset in_battle so reconnect can search again
                                if line.startswith("|win|") or line.startswith("|tie|"):
                                    self.in_battle = False
                            
                            self.q.put(message)
                    except Exception as e:
                        debug_print(f"WebSocket closed inner: {e}", "REMOTE")
            except Exception as e:
                debug_print(f"WebSocket connection failed: {e}", "REMOTE")
            
            if not getattr(self, '_closed', False):
                debug_print("Reconnecting in 2 seconds...", "REMOTE")
                await asyncio.sleep(2)

    def _login(self, challstr):
        debug_print("Attempting login...", "REMOTE")
        url = "https://play.pokemonshowdown.com/~~showdown/action.php"
        data = {
            "act": "login",
            "name": self.username,
            "pass": self.password,
            "challstr": challstr
        }
        try:
            r = requests.post(url, data=data)
            text = r.text
            if text.startswith("]"):
                text = text[1:]
            resp = json.loads(text)
            assertion = resp.get("assertion")
            if assertion:
                self.send(f"|/trn {self.username},0,{assertion}")
                debug_print("Sent login assertion", "REMOTE")
                # Wait for logged_in flag in a separate thread/task or just send it immediately after a delay
                self.loop.call_later(2.0, self._start_searching)
            else:
                debug_print(f"Login failed: {resp}", "REMOTE")
        except Exception as e:
            debug_print(f"Login error: {e}", "REMOTE")

    def _start_searching(self):
        if self.logged_in:
            # Don't search if already in an active battle
            if self.in_battle:
                debug_print("Already in a battle, skipping search", "REMOTE")
                return
            debug_print(f"Searching for {self.formatid}", "REMOTE")
            self.send(f"|/search {self.formatid}")
        else:
            self.loop.call_later(1.0, self._start_searching)

    def send(self, msg: str):
        msg = msg.strip()
        debug_print(f"Intercepted send: {msg}", "REMOTE")
        
        # Translate local >p1/p2 actions to remote /choose commands
        # E.g. ">p1 move 1" -> "battle-xxx|/choose move 1"
        if msg.startswith(">p1 ") or msg.startswith(">p2 "):
            parts = msg.split(" ", 1)
            if len(parts) == 2:
                command = parts[1]
                # In Showdown, team order in preview is done via /team
                if command.startswith("team "):
                    msg = f"{self.current_room}|/{command}"
                # /choose is used for move/switch
                elif command.startswith("move ") or command.startswith("switch ") or command == "default":
                    msg = f"{self.current_room}|/choose {command}"
                elif command == "forfeit":
                    msg = f"{self.current_room}|/forfeit"
                else:
                    msg = f"{self.current_room}|/{command}"
        
        if not msg.endswith("\n"):
            msg += "\n"
            
        debug_print(f"Actually sending: {msg.strip()}", "REMOTE")
        if self.ws and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.ws.send(msg), self.loop)

    def read(self):
        lines = []
        while not self.q.empty():
            msg = self.q.get()
            for line in msg.split('\n'):
                line = line.strip()
                if not line:
                    continue
                if line.startswith(">battle-"):
                    continue
                if line.startswith("|request|"):
                    lines.append(self.bot_side or "p2") # Side marker for parsers
                lines.append(line)
        return lines

    def wait_for_output(self, timeout=2.0):
        lines = []
        start_time = time.time()
        last_line_time = start_time
        
        while time.time() - start_time < timeout:
            got_lines = False
            while not self.q.empty():
                msg = self.q.get()
                for line in msg.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith(">battle-"):
                        continue
                    if line.startswith("|request|"):
                        lines.append("p2") # Fake side marker for cli.py
                    lines.append(line)
                last_line_time = time.time()
                got_lines = True
            
            if got_lines:
                time.sleep(0.1)
                continue
            
            if lines and (time.time() - last_line_time > 0.3):
                break
            
            time.sleep(0.05)
            
        return lines

    def close(self):
        self._closed = True
        if self.ws:
            asyncio.run_coroutine_threadsafe(self.ws.close(), self.loop)
        time.sleep(0.5)
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
