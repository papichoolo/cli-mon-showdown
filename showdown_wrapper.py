import subprocess
import threading
import queue
import time

DEBUG = False

def debug_print(message, category="DEBUG"):
    if DEBUG:
        print(f"[{category}] {message}")

class ShowdownWrapper:
    def __init__(self, ps_path="pokemon-showdown", formatid="gen7ou"):
        debug_print(f"Initializing ShowdownWrapper with path: {ps_path}, format: {formatid}", "WRAPPER")
        try:
            self.proc = subprocess.Popen(
                ["node", f"{ps_path}/pokemon-showdown", "simulate-battle"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            debug_print("Subprocess started successfully", "WRAPPER")
        except Exception as e:
            debug_print(f"Failed to start subprocess: {e}", "WRAPPER")
            raise
        
        self.q = queue.Queue()
        self.listener = threading.Thread(target=self._enqueue_output, daemon=True)
        self.listener.start()
        debug_print("Output listener thread started", "WRAPPER")
        self.send(f'>start {{"formatid":"{formatid}"}}')
        debug_print(f"Sent start command for format: {formatid}", "WRAPPER")

    def _enqueue_output(self):
        debug_print("Output listener started", "WRAPPER")
        try:
            for line in self.proc.stdout:
                debug_print(f"Received line: {line.strip()}", "WRAPPER")
                self.q.put(line)
        except Exception as e:
            debug_print(f"Error in output listener: {e}", "WRAPPER")
        debug_print("Output listener ended", "WRAPPER")

    def send(self, msg: str):
        if not msg.endswith("\n"):
            msg += "\n"
        debug_print(f"Sending: {msg.strip()}", "WRAPPER")
        try:
            self.proc.stdin.write(msg)
            self.proc.stdin.flush()
            debug_print("Message sent successfully", "WRAPPER")
        except Exception as e:
            debug_print(f"Error sending message: {e}", "WRAPPER")

    def read(self):
        lines = []
        while not self.q.empty():
            lines.append(self.q.get())
        debug_print(f"Read {len(lines)} lines from queue", "WRAPPER")
        return lines

    def wait_for_output(self, timeout=2.0):
        """Wait for output from the simulator for up to timeout seconds."""
        lines = []
        start_time = time.time()
        last_line_time = start_time
        
        while time.time() - start_time < timeout:
            # First collect any immediately available lines
            got_lines = False
            while not self.q.empty():
                line = self.q.get()
                lines.append(line)
                last_line_time = time.time()
                got_lines = True
            
            # If we got some lines recently, wait a bit more for any follow-up
            if got_lines:
                time.sleep(0.1)
                continue
            
            # If we have lines and haven't gotten any new ones for a while, we're probably done
            if lines and (time.time() - last_line_time > 0.3):
                break
            
            # If no lines yet, wait a short time before checking again
            time.sleep(0.05)
        
        debug_print(f"Wait for output collected {len(lines)} lines", "WRAPPER")
        return lines

    def close(self):
        self.proc.terminate()
