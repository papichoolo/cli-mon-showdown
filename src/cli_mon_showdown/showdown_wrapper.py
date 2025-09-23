import subprocess
import threading
import queue
import time
import os
from pathlib import Path

DEBUG = False

def debug_print(message, category="DEBUG"):
    if DEBUG:
        print(f"[{category}] {message}")

def _get_default_ps_path():
    """Get the default Pokemon Showdown path."""
    try:
        from . import get_pokemon_showdown_path
        return get_pokemon_showdown_path()
    except ImportError:
        return "pokemon-showdown"

def _check_pokemon_showdown_setup(ps_path):
    """Check if Pokemon Showdown is properly set up with dependencies."""
    ps_dir = Path(ps_path)
    
    # Check if pokemon-showdown executable exists
    ps_executable = ps_dir / "pokemon-showdown"
    if not ps_executable.exists():
        raise FileNotFoundError(
            f"Pokemon Showdown executable not found at {ps_executable}. "
            "Please ensure Pokemon Showdown is properly installed."
        )
    
    # Check if node_modules exists
    node_modules = ps_dir / "node_modules"
    if not node_modules.exists():
        package_json = ps_dir / "package.json"
        if package_json.exists():
            raise RuntimeError(
                f"Pokemon Showdown dependencies not installed. "
                f"Please run 'npm install' in the directory: {ps_dir}\n"
                f"Commands to run:\n"
                f"  cd {ps_dir}\n"
                f"  npm install\n"
                f"  node build"
            )
        else:
            raise FileNotFoundError(
                f"Pokemon Showdown package.json not found at {package_json}. "
                "Please ensure Pokemon Showdown is properly installed."
            )
    
    # Check if esbuild is installed with the right platform
    esbuild_dir = node_modules / "esbuild"
    if esbuild_dir.exists():
        # Try to detect platform-specific esbuild issues
        import platform
        system = platform.system().lower()
        arch = platform.machine().lower()
        
        if system == "windows":
            expected_platform = "win32"
        elif system == "darwin":
            expected_platform = "darwin"
        else:
            expected_platform = "linux"
            
        if arch in ["x86_64", "amd64"]:
            expected_arch = "x64"
        elif arch == "aarch64":
            expected_arch = "arm64"
        else:
            expected_arch = arch
            
        expected_esbuild = node_modules / f"@esbuild" / f"{expected_platform}-{expected_arch}"
        if not expected_esbuild.exists():
            raise RuntimeError(
                f"esbuild platform mismatch detected. Expected {expected_platform}-{expected_arch} but not found.\n"
                f"This happens when node_modules was installed on a different platform.\n"
                f"Please run the following commands to fix this:\n"
                f"  cd {ps_dir}\n"
                f"  rm -rf node_modules\n"
                f"  npm install\n"
                f"  node build"
            )

class ShowdownWrapper:
    def __init__(self, ps_path=None, formatid="gen7ou"):
        if ps_path is None:
            ps_path = _get_default_ps_path()
        debug_print(f"Initializing ShowdownWrapper with path: {ps_path}, format: {formatid}", "WRAPPER")
        
        # Check Pokemon Showdown setup before proceeding
        try:
            _check_pokemon_showdown_setup(ps_path)
        except (FileNotFoundError, RuntimeError) as e:
            debug_print(f"Pokemon Showdown setup error: {e}", "WRAPPER")
            raise
        
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
        
        # Queues and listener threads for stdout and stderr
        self.q = queue.Queue()
        self.err_q = queue.Queue()
        self.listener = threading.Thread(target=self._enqueue_output, daemon=True)
        self.err_listener = threading.Thread(target=self._enqueue_stderr, daemon=True)
        self.listener.start()
        self.err_listener.start()
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

    def _enqueue_stderr(self):
        """Continuously read simulator stderr to avoid deadlocks and aid debugging."""
        debug_print("Error listener started", "WRAPPER")
        try:
            for line in self.proc.stderr:
                # Mirror stderr to debug to surface simulator issues
                debug_print(f"[stderr] {line.strip()}", "WRAPPER")
                self.err_q.put(line)
        except Exception as e:
            debug_print(f"Error in error listener: {e}", "WRAPPER")
        debug_print("Error listener ended", "WRAPPER")

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

            # If the process died, stop waiting early
            if self.proc.poll() is not None:
                break

        debug_print(f"Wait for output collected {len(lines)} lines", "WRAPPER")
        return lines

    def close(self):
        try:
            self.proc.terminate()
        except Exception:
            pass

def generate_random_team(ps_path=None, formatid="gen7randombattle"):
    """Generates a random team for the given format."""
    if ps_path is None:
        ps_path = _get_default_ps_path()
    
    # Check Pokemon Showdown setup before proceeding
    try:
        _check_pokemon_showdown_setup(ps_path)
    except (FileNotFoundError, RuntimeError) as e:
        debug_print(f"Error generating random team: {e}", "WRAPPER")
        print(f"Error: Failed to generate random teams.\n{e}")
        return None
    
    try:
        result = subprocess.run(
            ["node", f"{ps_path}/pokemon-showdown", "generate-team", formatid],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        debug_print(f"Error generating random team: {e.stderr}", "WRAPPER")
        return None
    except Exception as e:
        debug_print(f"An unexpected error occurred while generating a team: {e}", "WRAPPER")
        return None
