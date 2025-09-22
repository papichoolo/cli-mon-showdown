import argparse
import json
import subprocess
import random
import time
import shutil
import sys
from typing import Dict, Optional, Tuple, List

try:
    from . import showdown_wrapper as showdown_wrapper
    from .showdown_wrapper import ShowdownWrapper
except ImportError:  # pragma: no cover - fallback for editable installs
    import showdown_wrapper  # type: ignore
    from showdown_wrapper import ShowdownWrapper  # type: ignore

# Import Gemini agent (optional, will fallback if not available)
try:
    from .gemini_agent import get_gemini_decision, init_gemini_agent
    GEMINI_AVAILABLE = True
except ImportError:
    try:
        from gemini_agent import get_gemini_decision, init_gemini_agent  # type: ignore
        GEMINI_AVAILABLE = True
    except ImportError:
        GEMINI_AVAILABLE = False

def debug_print(msg: str, prefix: str = "DEBUG"):
    """Print debug messages if debugging is enabled"""
    if showdown_wrapper.DEBUG:
        print(f"[{prefix}] {msg}")

# ---- Minimal ANSI UI window ----
ESC = "\033"

def _ansi(code: str) -> str:
    return f"{ESC}[{code}"

class GameWindow:
    """A simple in-terminal window to render battle state + event feed.

    Uses ANSI escape codes to draw a fixed window at the top of the terminal.
    Rendering saves/restores cursor position so prompts remain usable.
    """
    def __init__(self, enabled: bool = True, feed_lines: int = 8):
        self.enabled = enabled and sys.stdout.isatty()
        size = shutil.get_terminal_size(fallback=(80, 24))
        self.width = max(60, min(120, size.columns))
        self.feed_lines = max(15, min(25, feed_lines))  # Increased from 15 to 25 max lines
        self.feed: List[str] = []
        self.mounted = False
        self.last_render = ""  # Cache last render to avoid unnecessary redraws

    # --- helpers ---
    def _color(self, text: str, color: str) -> str:
        if not self.enabled:
            return text
        colors = {
            'red': '31m',
            'yellow': '33m',
            'green': '32m',
            'cyan': '36m',
            'magenta': '35m',
            'blue': '34m',
            'gray': '90m',
            'bold': '1m',
        }
        code = colors.get(color)
        return f"{_ansi(code) if code else ''}{text}{_ansi('0m')}" if code else text

    def _bar(self, hp: Optional[int], maxhp: Optional[int], hp_pct: Optional[int], width: int = 24) -> str:
        # Choose ratio source: prefer absolute, fallback to pct
        if isinstance(hp, int) and isinstance(maxhp, int) and maxhp > 0:
            ratio = max(0.0, min(1.0, hp / maxhp))
            pct = int(round(ratio * 100))
        elif isinstance(hp_pct, int):
            ratio = max(0.0, min(1.0, hp_pct / 100))
            pct = int(hp_pct)
        else:
            ratio = 0.0
            pct = 0

        filled = int(round(ratio * width))
        empty = width - filled
        # Color by percentage
        color = 'green' if pct >= 50 else ('yellow' if pct >= 20 else 'red')
        fill = self._color('█' * filled, color) if filled > 0 else ''
        rest = self._color('·' * empty, 'gray') if empty > 0 else ''
        return f"[{fill}{rest}] {pct:>3}%"

    # --- public API ---
    def add_feed(self, msg: Optional[str]):
        if not self.enabled or not msg:
            return
        # Normalize whitespace and clip
        msg = msg.replace('\n', ' ').strip()
        if not msg:  # Skip empty messages
            return
        
        # Wrap long messages instead of truncating
        max_line_length = self.width - 4  # Account for border characters
        if len(msg) > max_line_length:
            # Split message into wrapped lines
            words = msg.split(' ')
            lines = []
            current_line = ""
            
            for word in words:
                # If adding this word would exceed the line length
                if len(current_line) + len(word) + 1 > max_line_length:
                    if current_line:  # If we have content in current line
                        lines.append(current_line)
                        current_line = word
                    else:  # Single word is too long, truncate it
                        lines.append(word[:max_line_length - 3] + '...')
                        current_line = ""
                else:
                    if current_line:
                        current_line += " " + word
                    else:
                        current_line = word
            
            # Add the last line if it has content
            if current_line:
                lines.append(current_line)
            
            # Add each wrapped line to the feed
            for line in lines:
                # Avoid duplicates by checking recent messages
                if line not in self.feed[-5:]:
                    self.feed.append(line)
        else:
            # Message fits in one line
            if msg not in self.feed[-5:]:  # Check last 5 messages for duplicates
                self.feed.append(msg)
        
        # Keep only recent lines
        if len(self.feed) > 100:  # Reduce memory usage
            self.feed = self.feed[-100:]

    def mount(self):
        if not self.enabled or self.mounted:
            return
        # Clear screen and move cursor home
        sys.stdout.write(_ansi('2J'))  # clear screen
        sys.stdout.write(_ansi('H'))   # cursor to home
        sys.stdout.flush()
        self.mounted = True

    def render(self, battle: Dict[str, Dict[str, Optional[object]]], title: str = 'CLI-Mon Showdown'):
        if not self.enabled:
            return
        
        # Build window content
        w = self.width
        lines: List[str] = []
        top = '┌' + '─' * (w - 2) + '┐'
        bot = '└' + '─' * (w - 2) + '┘'
        header = f" {title} "
        header = header[: w - 2]
        pad = (w - 2 - len(header))
        header_line = '│' + self._color(header + ' ' * pad, 'bold') + '│'

        # Battle lines
        def side_line(label: str, side: Dict[str, Optional[object]]) -> str:
            name = str(side.get('name') or '?')
            hp = side.get('hp')
            maxhp = side.get('maxhp')
            hp_pct = side.get('hp_pct')
            fainted = bool(side.get('fainted'))
            status = side.get('status') or ''
            if fainted:
                bar = self._color('[' + 'X' * 24 + ']' + '  0%', 'red')
            else:
                bar = self._bar(hp if isinstance(hp, int) else None,
                                 maxhp if isinstance(maxhp, int) else None,
                                 hp_pct if isinstance(hp_pct, int) else None,
                                 width=24)
            left = f"{label} {name}"
            right = f"{bar}"
            if status:
                status_colors = {'par': 'yellow', 'slp': 'blue', 'frz': 'cyan', 'brn': 'red', 'psn': 'magenta', 'tox': 'magenta'}
                status_color = status_colors.get(status, 'gray')
                right += f"  [{self._color(status.upper(), status_color)}]"
            # Compose with padding
            content = (left + ' ' * (w - 2 - len(left) - len(right)) + right)
            if len(content) > w - 2:
                content = content[: w - 5] + '...'
            return '│' + content.ljust(w - 2) + '│'

        lines.append(top)
        lines.append(header_line)
        lines.append('│' + (' ' * (w - 2)) + '│')
        lines.append(side_line('P1', battle.get('p1', {})))
        lines.append(side_line('P2', battle.get('p2', {})))
        lines.append('│' + (' ' * (w - 2)) + '│')

        # Feed header and content
        feed_title = self._color(' Battle Log ', 'cyan')
        feed_header = '│' + (feed_title + '─' * max(0, (w - 2 - len(' Battle Log ') - 1))).ljust(w - 2, '─') + '│'
        lines.append(feed_header)
        # Show more lines in the feed (up to twice the feed_lines)
        max_feed_display = self.feed_lines * 2
        recent = self.feed[-max_feed_display:]
        # Only display the last feed_lines lines, but allow scrolling if needed
        display_lines = recent[-self.feed_lines:]
        for text in display_lines:
            lines.append('│ ' + text.ljust(w - 3) + '│')
        # Pad with empty lines if display_lines is shorter than feed_lines
        for _ in range(self.feed_lines - len(display_lines)):
            lines.append('│ ' + ''.ljust(w - 3) + '│')

        lines.append(bot)

        # Check if content changed to avoid unnecessary redraws
        new_render = '\n'.join(lines)
        if new_render == self.last_render:
            return
        self.last_render = new_render

        # Render at top-left with improved cursor handling
        try:
            sys.stdout.write(_ansi('s'))   # save cursor
            sys.stdout.write(_ansi('H'))   # home
            # Clear the exact area we're writing to prevent artifacts
            for i in range(len(lines)):
                sys.stdout.write(_ansi(f'{i+1};1H'))  # Move to line i+1, column 1
                sys.stdout.write(' ' * w)  # Clear the line
            sys.stdout.write(_ansi('H'))   # Return to home
            sys.stdout.write(new_render)
            sys.stdout.write(_ansi('u'))   # restore cursor
            sys.stdout.flush()
        except (OSError, IOError) as e:
            # Fallback to simple rendering if ANSI fails
            debug_print(f"ANSI rendering failed: {e}, falling back to simple print", "UI")
            print(new_render)
        except Exception as e:
            # Log unexpected UI errors but don't crash
            debug_print(f"Unexpected UI rendering error: {e}", "UI_ERROR")
            print(new_render)

# ---- Lightweight 1v1 battle state for reactive UI ----
BattleSide = Dict[str, Optional[object]]  # name, hp, maxhp, status, fainted

# Monotonic per-side request sequence used to dedupe actions when rqid is missing/unchanged
_REQUEST_SEQ: Dict[str, int] = {"p1": 0, "p2": 0}

def _new_battle_state() -> Dict[str, BattleSide]:
    return {
        'p1': {'name': None, 'hp': None, 'maxhp': None, 'hp_pct': None, 'status': None, 'fainted': False},
        'p2': {'name': None, 'hp': None, 'maxhp': None, 'hp_pct': None, 'status': None, 'fainted': False},
    }

def _parse_actor(token: str) -> Tuple[Optional[str], Optional[str]]:
    # token like 'p1a: Charizard'
    if ': ' in token:
        side_part, name = token.split(': ', 1)
        side = side_part[:2] if side_part.startswith(('p1', 'p2')) else None
        return side, name
    return None, None

def _parse_hp_token(tok: str) -> Tuple[Optional[int], Optional[int], Optional[int], bool]:
    """Parse an HP token from Showdown stream.
    Returns (hp, maxhp, hp_pct, fainted).

    Handles forms like:
      - "182/319"
      - "182/319 slp" (status suffix)
      - "75/100" (percentage style)
      - "0 fnt" or "0/352 fnt" (fainted)
    """
    if not tok:
        return None, None, None, False
    s = tok.strip()
    # Faint detection first
    if 'fnt' in s:
        return 0, None, 0, True

    # Remove any trailing annotations (status, brackets info, etc.)
    # Keep only the first whitespace-separated token which should be the HP form
    first = s.split(' ', 1)[0]

    # Now parse the HP form
    if '/' in first:
        cur, maximum = first.split('/', 1)
        try:
            cur_i = int(cur)
            max_i = int(maximum)
        except ValueError:
            return None, None, None, False
        # Percentage style like 75/100
        if max_i == 100:
            return None, None, cur_i, False  # return percentage only
        # Absolute style like 182/319
        pct = int(round((cur_i / max_i) * 100)) if max_i else None
        return cur_i, max_i, pct, False
    else:
        # Single number without '/', treat as current HP if purely numeric (rare)
        try:
            cur_i = int(first)
            # Without a max, we can't compute pct; leave unknown
            return cur_i, None, None, False
        except ValueError:
            return None, None, None, False

def _update_battle_state_from_line(line: str, battle: Dict[str, BattleSide]) -> Tuple[bool, bool]:
    """Update battle state from a battle line. Returns (changed, error_detected)."""
    debug_print(f"Processing battle line: {line.strip()}", "BATTLE_STATE")
    changed = False
    error_detected = False
    if not line or '|' not in line:
        return False, False
    parts = line.strip().split('|')
    # parts[0] is '' usually for battle messages
    if len(parts) < 2:
        return False, False
    tag = parts[1]
    debug_print(f"Battle tag: {tag}, parts: {len(parts)}", "BATTLE_STATE")
    
    # Handle error messages
    if tag == 'error' and len(parts) >= 3:
        error_msg = parts[2]
        debug_print(f"Battle error detected: {error_msg}", "BATTLE_STATE")
        error_detected = True
    
    # Handle successful moves (reset AI error count)
    if tag == 'move' and len(parts) >= 3:
        side, _ = _parse_actor(parts[2])
        if side == 'p2':
            # AI successfully made a move, reset error count
            debug_print("AI move successful, resetting error count", "BATTLE_STATE")
            # Note: We can't directly access ai_error_count here, will handle in caller
    
    if tag in ('switch', 'drag') and len(parts) >= 3:
        side, name = _parse_actor(parts[2])
        debug_print(f"Pokemon switch/drag - Side: {side}, Name: {name}", "BATTLE_STATE")
        if side in battle and name:
            if battle[side].get('name') != name:
                battle[side]['name'] = name
                # Reset status on switch to avoid carrying over from previous Pokemon
                if battle[side].get('status') is not None:
                    battle[side]['status'] = None
                # keep hp until we get a proper hp token; reset fainted
                battle[side]['fainted'] = False
                changed = True
            # switch lines often include an HP token at parts[4]
            if len(parts) >= 5:
                hp, maxhp, hp_pct, fainted = _parse_hp_token(parts[4])
                if fainted:
                    if battle[side].get('fainted') is not True:
                        battle[side]['fainted'] = True
                        battle[side]['hp'] = 0
                        changed = True
                else:
                    # For switch lines, we get both absolute and percentage HP
                    # The first line usually has absolute HP, second has percentage
                    if hp is not None and maxhp is not None and maxhp != 100:
                        # This is absolute HP
                        if battle[side].get('hp') != hp:
                            battle[side]['hp'] = hp
                            changed = True
                        if battle[side].get('maxhp') != maxhp:
                            battle[side]['maxhp'] = maxhp
                            changed = True
                        if hp_pct is not None and battle[side].get('hp_pct') != hp_pct:
                            battle[side]['hp_pct'] = hp_pct
                            changed = True
                    elif hp_pct is not None and maxhp == 100:
                        # This is percentage HP, don't overwrite maxhp if we already have absolute
                        if battle[side].get('hp_pct') != hp_pct:
                            battle[side]['hp_pct'] = hp_pct
                            changed = True
                        # Update absolute HP if we know maxhp
                        known_max = battle[side].get('maxhp')
                        if known_max and known_max != 100:
                            abs_hp = int(round(hp_pct * known_max / 100))
                            if battle[side].get('hp') != abs_hp:
                                battle[side]['hp'] = abs_hp
                                changed = True
    elif tag in ('-damage', '-heal', '-sethp') and len(parts) >= 4:
        side, _ = _parse_actor(parts[2])
        debug_print(f"HP change - Side: {side}, Tag: {tag}", "BATTLE_STATE")
        if side in battle:
            hp, maxhp, hp_pct, fainted = _parse_hp_token(parts[3])
            debug_print(f"HP token parsed - HP: {hp}, MaxHP: {maxhp}, Fainted: {fainted}", "BATTLE_STATE")
            if fainted:
                if battle[side].get('fainted') is not True:
                    battle[side]['fainted'] = True
                    battle[side]['hp'] = 0
                    changed = True
            else:
                known_max = battle[side].get('maxhp')
                # Handle percentage-style reports like 71/100
                if hp_pct is not None and known_max and hp is None:
                    # This is a percentage update, convert to absolute
                    abs_hp = int(round(hp_pct * known_max / 100))
                    if battle[side].get('hp') != abs_hp:
                        battle[side]['hp'] = abs_hp
                        changed = True
                    if battle[side].get('hp_pct') != hp_pct:
                        battle[side]['hp_pct'] = hp_pct
                        changed = True
                elif hp is not None and maxhp is not None:
                    # Absolute HP update
                    if battle[side].get('hp') != hp:
                        battle[side]['hp'] = hp
                        changed = True
                    if battle[side].get('maxhp') != maxhp:
                        battle[side]['maxhp'] = maxhp
                        changed = True
                    if hp_pct is not None and battle[side].get('hp_pct') != hp_pct:
                        battle[side]['hp_pct'] = hp_pct
                        changed = True
    elif tag == 'faint' and len(parts) >= 3:
        side, _ = _parse_actor(parts[2])
        if side in battle and battle[side].get('fainted') is not True:
            battle[side]['fainted'] = True
            battle[side]['hp'] = 0
            changed = True
    elif tag == '-status' and len(parts) >= 4:
        side, _ = _parse_actor(parts[2])
        status = parts[3]
        if side in battle and battle[side].get('status') != status:
            battle[side]['status'] = status
            changed = True
    elif tag == '-curestatus' and len(parts) >= 4:
        side, _ = _parse_actor(parts[2])
        if side in battle and battle[side].get('status') is not None:
            battle[side]['status'] = None
            changed = True
    return changed, error_detected

def _hp_bar_line(side_label: str, side: BattleSide, width: int = 20) -> str:
    name = side.get('name') or '?'
    hp = side.get('hp')
    maxhp = side.get('maxhp')
    hp_pct = side.get('hp_pct')
    fainted = side.get('fainted')
    status = side.get('status')
    if fainted:
        bar = '[' + 'X' * width + ']'
        info = 'fainted'
    elif isinstance(hp, int) and isinstance(maxhp, int) and maxhp > 0:
        ratio = max(0.0, min(1.0, hp / maxhp))
        filled = int(round(ratio * width))
        bar = '[' + '█' * filled + '·' * (width - filled) + ']'
        pct = int(round(ratio * 100))
        info = f"{hp}/{maxhp} ({pct}%)"
    elif isinstance(hp_pct, int):
        ratio = max(0.0, min(1.0, hp_pct / 100))
        filled = int(round(ratio * width))
        bar = '[' + '█' * filled + '·' * (width - filled) + ']'
        info = f"{hp_pct}%"
    else:
        bar = '[' + '·' * width + ']'
        info = '--/--'
    status_str = f" [{status}]" if status else ''
    return f"{side_label} {name} {bar} {info}{status_str}"

def _render_overlay(battle: Dict[str, BattleSide]) -> str:
    # Legacy overlay for non-window mode
    return ("\n" +
            _hp_bar_line('P1:', battle['p1']) + "\n" +
            _hp_bar_line('P2:', battle['p2']) + "\n")

# ---- Humanized feed helpers ----
def _side_label(side: Optional[str]) -> str:
    return side.upper() if side in ("p1", "p2") else "?"

def _humanize_line(line: str) -> Optional[str]:
    if '|' not in line:
        return None
    parts = line.strip().split('|')
    if len(parts) < 2:
        return None
    tag = parts[1]
    
    # Skip empty or technical messages
    if tag in ('', 't:', 'gametype', 'gen', 'tier', 'rule', 'clearpoke', 'poke', 'teampreview', 
               'sideupdate', 'split', 'teamsize', 'start', 'upkeep', 'request'):
        return None
    
    if tag == 'turn' and len(parts) >= 3:
        return f"-- Turn {parts[2]} --"
    if tag == 'move' and len(parts) >= 4:
        side, name = _parse_actor(parts[2])
        move = parts[3]
        target = None
        if len(parts) >= 5:
            _, target_name = _parse_actor(parts[4])
            target = target_name
        base = f"{_side_label(side)} {name} used {move}"
        if target:
            base += f" on {target}"
        return base
    if tag in ('-supereffective', '-resisted', '-crit', '-miss', '-immune', '-fail'):
        mapping = {
            '-supereffective': "It's super effective!",
            '-resisted': "It's not very effective...",
            '-crit': "A critical hit!",
            '-miss': "It missed!",
            '-immune': "It had no effect.",
            '-fail': "But it failed!",
        }
        return mapping.get(tag)
    if tag in ('-damage', '-heal', '-sethp') and len(parts) >= 4:
        side, name = _parse_actor(parts[2])
        hp = parts[3]
        if 'fnt' in hp:
            return f"{name} fainted!"
        # Skip percentage-only updates to reduce noise
        if hp.endswith('/100'):
            return None
        return f"{name}: {hp}"
    if tag in ('-residual', '-recoil', '-drain') and len(parts) >= 4:
        side, name = _parse_actor(parts[2])
        if tag == '-residual':
            return f"{name} was hurt by residual damage!"
        if tag == '-recoil':
            return f"{name} was hurt by recoil!"
        if tag == '-drain':
            return f"{name} absorbed health!"
    if tag == 'faint' and len(parts) >= 3:
        _, name = _parse_actor(parts[2])
        return f"{name} fainted!"
    if tag in ('switch', 'drag') and len(parts) >= 3:
        side, name = _parse_actor(parts[2])
        verb = "sent out" if tag == 'switch' else "was dragged out"
        msg = f"{_side_label(side)} {verb} {name}"
        if len(parts) >= 5:
            hp = parts[4]
            if hp:
                msg += f" ({hp})"
        return msg
    if tag == 'mega' and len(parts) >= 4:
        side, name = _parse_actor(parts[2])
        return f"{name} Mega-Evolved!"
    if tag == '-formechange' and len(parts) >= 4:
        side, name = _parse_actor(parts[2])
        new_form = parts[3]
        return f"{name} transformed into {new_form}!"
    if tag == 'detailschange' and len(parts) >= 4:
        side, name = _parse_actor(parts[2])
        details = parts[3]
        return f"{name} changed to {details}!"
    if tag == '-boost' and len(parts) >= 5:
        side, name = _parse_actor(parts[2])
        stat = parts[3]
        amount = parts[4]
        levels = "sharply " if int(amount) >= 2 else ""
        return f"{name}'s {stat} {levels}rose!"
    if tag == '-unboost' and len(parts) >= 5:
        side, name = _parse_actor(parts[2])
        stat = parts[3]
        amount = parts[4]
        levels = "sharply " if int(amount) >= 2 else ""
        return f"{name}'s {stat} {levels}fell!"
    if tag == '-clearboost' and len(parts) >= 3:
        side, name = _parse_actor(parts[2])
        return f"{name}'s stat changes were cleared!"
    if tag == '-clearallboost':
        return "All stat changes were reset!"
    if tag == '-status' and len(parts) >= 4:
        side, name = _parse_actor(parts[2])
        status = parts[3]
        status_names = {
            'par': 'paralyzed',
            'slp': 'asleep', 
            'frz': 'frozen',
            'brn': 'burned',
            'psn': 'poisoned',
            'tox': 'badly poisoned'
        }
        status_text = status_names.get(status, status)
        return f"{name} was {status_text}!"
    if tag == '-curestatus' and len(parts) >= 4:
        side, name = _parse_actor(parts[2])
        status = parts[3]
        return f"{name} was cured of {status}!"
    if tag == '-start' and len(parts) >= 4:
        side, name = _parse_actor(parts[2])
        effect = parts[3]
        if effect == 'typechange' and len(parts) >= 5:
            return f"{name} became {parts[4]} type!"
        elif 'ability:' in effect:
            ability_name = effect.split('ability: ')[1]
            return f"{name}'s {ability_name} activated!"
        return f"{name} started {effect}"
    if tag == '-end' and len(parts) >= 4:
        side, name = _parse_actor(parts[2])
        effect = parts[3]
        return f"{name} ended {effect}"
    if tag == 'win' and len(parts) >= 3:
        return f"🎉 Winner: {parts[2]} 🎉"
    if tag == 'tie':
        return "The battle ended in a tie!"
    if tag == '-weather' and len(parts) >= 3:
        weather = parts[2]
        weather_names = {
            'sunnyday': 'harsh sunlight',
            'raindance': 'rain',
            'sandstorm': 'sandstorm',
            'hail': 'hail'
        }
        weather_text = weather_names.get(weather, weather)
        return f"The weather became {weather_text}!"
    if tag == '-fieldstart' and len(parts) >= 3:
        field_effect = parts[2]
        if 'Stealth Rock' in field_effect:
            return "Stealth Rock was set up!"
        elif 'Spikes' in field_effect:
            return "Spikes were set up!"
        elif 'Toxic Spikes' in field_effect:
            return "Toxic Spikes were set up!"
        elif 'Sticky Web' in field_effect:
            return "Sticky Web was set up!"
        return f"Field effect: {field_effect}"
    if tag == '-fieldend' and len(parts) >= 3:
        field_effect = parts[2]
        if 'Stealth Rock' in field_effect:
            return "Stealth Rock was removed!"
        elif 'Spikes' in field_effect:
            return "Spikes were removed!"
        elif 'Toxic Spikes' in field_effect:
            return "Toxic Spikes were removed!"
        elif 'Sticky Web' in field_effect:
            return "Sticky Web was removed!"
        return f"Field effect ended: {field_effect}"
    if tag in ('-sidestart', '-sideend') and len(parts) >= 4:
        side = parts[2]
        effect = parts[3]
        if 'move:' in effect:
            effect = effect.split('move: ')[1]
        if tag == '-sidestart':
            return f"{effect} protected {_side_label(side)}'s team."
        return f"{_side_label(side)}'s {effect} wore off."
    if tag in ('-item', '-enditem') and len(parts) >= 4:
        side, name = _parse_actor(parts[2])
        item = parts[3]
        if tag == '-item':
            return f"{name} obtained {item}!"
        return f"{name} consumed its {item}!"
    if tag in ('-ability', 'ability') and len(parts) >= 4:
        side, name = _parse_actor(parts[2])
        ability = parts[3]
        if tag == 'ability':
            return f"{name}'s {ability} was revealed!"
        return f"{name}'s {ability} activated!"
    if tag == 'cant' and len(parts) >= 4:
        side, name = _parse_actor(parts[2])
        reason = parts[3]
        if reason == 'flinch':
            return f"{name} flinched and couldn't move!"
        elif reason == 'par':
            return f"{name} is paralyzed and can't move!"
        elif reason == 'slp':
            return f"{name} is fast asleep!"
        return f"{name} can't move due to {reason}!"
    if tag == '-activate' and len(parts) >= 4:
        side, name = _parse_actor(parts[2])
        effect = parts[3]
        if 'ability:' in effect:
            ability_name = effect.split('ability: ')[1]
            return f"{name}'s {ability_name} activated!"
        return None  # Skip other activation messages as they're often too technical
    
    return None

def _process_output(out_lines, humanize: bool, active_side: str, requests: Dict[str, dict], shown_rqid: Dict[str, Optional[int]], battle: Dict[str, BattleSide], ai_error_count: Dict[str, int], current_turn: int = 0, ui: Optional[GameWindow] = None) -> Tuple[Optional[str], bool, int]:
    if not out_lines:
        return None, False, current_turn
    winner: Optional[str] = None
    overlay_changed = False
    player_error_detected = False
    
    # Parse requests from the entire stream first
    debug_print(f"Parsing stream for requests from {len(out_lines)} lines", "REQUESTS")
    _parse_stream_lines(out_lines, requests)
    debug_print(f"Requests after parsing: {list(requests.keys())}", "REQUESTS")
    
    feed_changed = False
    seen_messages = set()  # Track messages we've already added to avoid duplicates
    
    for line in out_lines:
        # New turn: clear shown request IDs so AI/player can act again
        # Some simulator requests omit or reuse rqid across turns; resetting here
        # ensures we don't suppress valid actions on a new turn.
        if '|turn|' in line:
            shown_rqid['p1'] = None
            shown_rqid['p2'] = None
            # Extract turn number for LLM agent context
            try:
                parts = line.split('|turn|')
                if len(parts) > 1:
                    current_turn = int(parts[1].strip())
            except (ValueError, IndexError):
                pass  # Keep existing turn number if parsing fails
            debug_print("New turn detected; reset shown_rqid for both sides", "REQUESTS")
        # Check for player errors first to handle error recovery
        if '|error|' in line and ('Invalid choice' in line or 'Unavailable choice' in line):
            debug_print(f"Player error detected: {line.strip()}", "ERROR_RECOVERY")
            player_error_detected = True
            # Reset the shown request ID to force re-prompting
            for side in shown_rqid:
                if side == active_side:
                    shown_rqid[side] = None
                    debug_print(f"Reset request ID for {side} to force re-prompt", "ERROR_RECOVERY")
            # Add error message to UI
            error_msg = line.split('|error|', 1)[1] if '|error|' in line else "Invalid choice"
            if ui and ui.enabled:
                ui.add_feed(f"⚠️ {error_msg}")
                feed_changed = True
            else:
                print(f"\n⚠️ {error_msg}")
        
        # Process battle state
        try:
            state_changed, error_detected = _update_battle_state_from_line(line, battle)
            if state_changed:
                overlay_changed = True
            # Track AI errors for p2
            if error_detected and 'p2' in line:
                ai_error_count['p2'] += 1
                debug_print(f"AI error detected, count: {ai_error_count['p2']}", "AI")
            # Reset AI error count on successful moves
            elif '|move|p2' in line:
                ai_error_count['p2'] = 0
                debug_print("AI move successful, error count reset", "AI")
        except Exception as e:
            debug_print(f"Error processing battle state line '{line.strip()}': {e}", "ERROR")
            # Continue processing other lines instead of failing silently
        
        # Handle UI vs non-UI output differently
        if ui and ui.enabled:
            # For UI mode, only add meaningful events to the feed
            if humanize:
                msg = _humanize_line(line)
                if msg and msg not in seen_messages:
                    ui.add_feed(msg)
                    seen_messages.add(msg)
                    feed_changed = True
            else:
                # Raw mode: only add non-empty lines and avoid duplicates
                clean_line = line.strip()
                if clean_line and clean_line not in seen_messages and not clean_line.startswith('|'):
                    ui.add_feed(clean_line)
                    seen_messages.add(clean_line)
                    feed_changed = True
        else:
            # Non-UI mode: preserve original behavior
            if humanize:
                msg = _humanize_line(line)
                if msg:
                    print(msg)
            else:
                print(line, end='')
        
        # Check for winner
        if '|win|' in line:
            winner = line.split('|win|', 1)[1].strip() or 'Unknown'
    
    # Overlay/UI refresh only once at the end
    if ui and ui.enabled:
        if overlay_changed or feed_changed:
            ui.render(battle)
    else:
        if overlay_changed:
            print(_render_overlay(battle))
    
    # Return winner and whether a player error was detected
    return winner, player_error_detected, current_turn

def pack_team(path: str, formatname: str = "gen7ou", ps_path: str = None) -> str:
    import os
    from . import get_pokemon_showdown_path
    
    if ps_path is None:
        ps_path = get_pokemon_showdown_path()
    
    # First check if the team file exists
    if not os.path.exists(path):
        raise RuntimeError(f"Team file not found: {path}")
    
    try:
        # Read the team file content
        with open(path, 'r', encoding='utf-8') as f:
            team_content = f.read()
    except IOError as e:
        debug_print(f"File read error for {path}: {e}", "TEAM_ERROR")
        raise RuntimeError(f"Could not read team file {path}: {e}")
    
    try:
        # First, pack the team using Pokemon Showdown
        pack_result = subprocess.run(
            ["node", f"{ps_path}/pokemon-showdown", "pack-team"],
            input=team_content,
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )
        packed_team = pack_result.stdout.strip()
        
    except subprocess.TimeoutExpired as e:
        debug_print(f"Team packing timeout for {path}: {e}", "TEAM_ERROR")
        raise RuntimeError(f"Team packing timed out for {path}")
    except subprocess.CalledProcessError as e:
        debug_print(f"Team packing failed for {path}: {e.stderr}", "TEAM_ERROR")
        raise RuntimeError(f"Failed to pack team {path}: {e.stderr}")
    except FileNotFoundError as e:
        debug_print(f"Node.js or pokemon-showdown not found when packing {path}: {e}", "TEAM_ERROR")
        raise RuntimeError("Node.js not found or pokemon-showdown directory missing")
    
    try:
        # Then validate the team using the specified format
        validate_result = subprocess.run(
            ["node", f"{ps_path}/pokemon-showdown", "validate-team", formatname],
            input=team_content,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Check if there are validation errors
        if validate_result.returncode != 0:
            error_output = validate_result.stderr.strip()
            if error_output:
                # Display validation errors clearly
                print(f"\n⚠️ Team validation errors for {path}:")
                print(f"Format: {formatname}")
                print("=" * 50)
                print(error_output)
                print("=" * 50)
                raise RuntimeError(f"Team validation failed for {path} in format {formatname}:\n{error_output}")
            else:
                # If no stderr but non-zero exit code, there might be banned Pokemon/moves
                print(f"\n⚠️ Team validation failed for {path} in format {formatname}")
                print("The team may contain banned Pokemon, moves, or items for this format.")
                raise RuntimeError(f"Team validation failed for {path} in format {formatname}")
        
    except subprocess.TimeoutExpired as e:
        debug_print(f"Team validation timeout for {path}: {e}", "TEAM_ERROR")
        raise RuntimeError(f"Team validation timed out for {path}")
    except subprocess.CalledProcessError as e:
        debug_print(f"Team validation failed for {path}: {e.stderr}", "TEAM_ERROR")
        raise RuntimeError(f"Failed to validate team {path}: {e.stderr}")
    except FileNotFoundError as e:
        debug_print(f"Node.js or pokemon-showdown not found when validating {path}: {e}", "TEAM_ERROR")
        raise RuntimeError("Node.js not found or pokemon-showdown directory missing")
    
    # If validation passed, return the packed team
    debug_print(f"Team {path} packed and validated successfully for format {formatname}", "TEAM")
    return packed_team

def _parse_stream_lines(lines, requests: Dict[str, dict]) -> None:
    """Update requests dict from simulator stream output."""
    current: Optional[str] = None
    for raw in lines:
        line = raw.rstrip('\n')
        # Channel markers can be 'p1'/'p2'/'omniscient' or with a leading '>'
        if line in ('p1', 'p2', 'omniscient'):
            current = line
            continue
        if line.startswith('>') and ' ' not in line:
            current = line[1:].strip()
            continue
        if '|request|' in line and current in ('p1', 'p2'):
            try:
                payload = line.split('|request|', 1)[1]
                req = json.loads(payload)
                # Attach a monotonically increasing sequence number per side
                try:
                    _REQUEST_SEQ[current] = _REQUEST_SEQ.get(current, 0) + 1
                except Exception:
                    # Defensive fallback
                    _REQUEST_SEQ[current] = 1
                req['_seq'] = _REQUEST_SEQ[current]
                requests[current] = req
                debug_print(f"Parsed request for {current}: {list(req.keys())}", "REQUESTS")
            except (json.JSONDecodeError, IndexError) as e:
                # Log malformed JSON but keep last good request
                debug_print(f"Malformed request JSON for {current}: {e}", "REQUESTS_ERROR")
            except Exception as e:
                # Log unexpected parsing errors
                debug_print(f"Unexpected error parsing request for {current}: {e}", "REQUESTS_ERROR")

def _get_available_moves(req: dict) -> List[dict]:
    """Get list of available moves from request."""
    if not req or 'active' not in req or not req['active']:
        return []
    active = req['active'][0]
    moves = active.get('moves', [])
    available_moves = []
    for i, m in enumerate(moves, 1):
        if not m.get('disabled'):
            # Add the original index to track the move's position
            move_copy = m.copy()
            move_copy['original_index'] = i
            available_moves.append(move_copy)
    return available_moves

def _get_available_switches(req: dict) -> List[dict]:
    """Get list of available Pokemon to switch to."""
    if not req:
        return []
    side = req.get('side') or {}
    pokemon = side.get('pokemon') or []
    available = []
    for i, p in enumerate(pokemon, start=1):
        condition = p.get('condition', '')
        if 'fnt' not in condition:  # Not fainted
            available.append({'index': i, 'pokemon': p})
    return available

def _get_forced_switch_options(req: dict) -> List[dict]:
    """Get list of Pokemon available for forced switch (excludes active Pokemon)."""
    if not req:
        return []
    side = req.get('side') or {}
    pokemon = side.get('pokemon') or []
    available = []
    
    # In forced switch scenarios, we need to exclude the currently active Pokemon
    # The active Pokemon is typically the first one in the list that's not fainted
    # but since it just fainted, we look for the first non-fainted Pokemon that isn't slot 1
    for i, p in enumerate(pokemon, start=1):
        condition = p.get('condition', '')
        # Skip fainted Pokemon and also skip the first slot in forced switch
        # (since that's typically where the fainted active Pokemon was)
        if 'fnt' not in condition and i > 1:
            available.append({'index': i, 'pokemon': p})
    
    # If we found no options excluding slot 1, then check all non-fainted
    # (this handles edge cases)
    if not available:
        for i, p in enumerate(pokemon, start=1):
            condition = p.get('condition', '')
            if 'fnt' not in condition:
                available.append({'index': i, 'pokemon': p})
    
    return available

def _create_agent_observation(ai_req: dict, battle: Dict[str, BattleSide], ui: Optional[GameWindow] = None, current_turn: int = 0) -> dict:
    """Create observation payload for the LLM agent."""
    if not ai_req:
        return {}
    
    # Extract active Pokemon information
    active_data = {}
    if ai_req.get('active') and len(ai_req['active']) > 0:
        active_pokemon = ai_req['active'][0]
        active_data = {
            'moves': active_pokemon.get('moves', []),
            'canMegaEvo': active_pokemon.get('canMegaEvo', False),
            'canZMove': active_pokemon.get('canZMove'),
            'canUltraBurst': active_pokemon.get('canUltraBurst', False),
            'trapped': active_pokemon.get('trapped', False)
        }
    
    # Extract bench information (team summary)
    bench_data = []
    side_data = ai_req.get('side', {})
    pokemon_list = side_data.get('pokemon', [])
    
    for i, pokemon in enumerate(pokemon_list, start=1):
        # Extract condition info (HP and status)
        condition = pokemon.get('condition', '')
        hp_info = {'fainted': 'fnt' in condition}
        
        # Parse HP from condition (e.g., "183/281" or "58/100")
        if condition and not hp_info['fainted']:
            if '/' in condition:
                hp_part = condition.split()[0] if ' ' in condition else condition
                if '/' in hp_part:
                    try:
                        current_hp, max_hp = hp_part.split('/')
                        hp_info['current_hp'] = int(current_hp)
                        hp_info['max_hp'] = int(max_hp)
                        hp_info['hp_percent'] = int(round((int(current_hp) / int(max_hp)) * 100))
                    except ValueError:
                        pass
        
        # Extract status condition
        status = None
        if ' ' in condition:
            status_part = condition.split(' ', 1)[1]
            if status_part not in ['fnt']:
                status = status_part
        
        bench_data.append({
            'index': i,
            'species': pokemon.get('details', '').split(',')[0] if pokemon.get('details') else 'Unknown',
            'details': pokemon.get('details', ''),
            'condition': condition,
            'hp_info': hp_info,
            'status': status,
            'active': pokemon.get('active', False),
            'item': pokemon.get('item'),
            'ability': pokemon.get('ability'),
            'stats': pokemon.get('stats'),
            'moves': pokemon.get('moves')
        })
    
    # Extract opponent information (public battle state)
    opponent_data = battle.get('p1', {})
    
    # Get available moves
    available_moves = []
    moves_data = _get_available_moves(ai_req)
    for i, move in enumerate(moves_data):
        available_moves.append({
            'index': move.get('original_index', i + 1),
            'id': move.get('id', ''),
            'move': move.get('move', ''),
            'pp': move.get('pp'),
            'maxpp': move.get('maxpp'),
            'target': move.get('target', ''),
            'disabled': move.get('disabled', False)
        })
    
    # Get available switches
    available_switches = []
    switches_data = _get_available_switches(ai_req)
    for switch in switches_data:
        pokemon = switch['pokemon']
        # Skip the currently active Pokemon
        if not pokemon.get('active', False):
            available_switches.append({
                'index': switch['index'],
                'species': pokemon.get('details', '').split(',')[0] if pokemon.get('details') else 'Unknown',
                'details': pokemon.get('details', ''),
                'condition': pokemon.get('condition', ''),
                'hp_status': pokemon.get('condition', '').split()[0] if pokemon.get('condition') else ''
            })
    
    # Get recent events from the UI feed
    recent_events = []
    if ui and ui.enabled and hasattr(ui, 'feed'):
        # Get the last 10 entries from the feed for context
        recent_events = ui.feed[-10:] if ui.feed else []
    
    # Check if this is a forced switch scenario
    is_forced_switch = bool((ai_req.get('forceSwitch') or [False])[0])
    
    # Extract weather and terrain for clearer representation
    weather = ai_req.get('weather', None)
    field_conditions = ai_req.get('field', {})
    
    # Extract terrain specifically from field conditions if present
    terrain = None
    for key in field_conditions.keys():
        if 'terrain' in key.lower():
            terrain = key
            break
    
    # Create the complete observation
    observation = {
        'turn': current_turn,
        'active': active_data,
        'bench': bench_data,
        'opponent_active': {
            'species': opponent_data.get('name'),
            'hp_percent': opponent_data.get('hp_pct'),
            'status': opponent_data.get('status'),
            'fainted': opponent_data.get('fainted', False)
        },
        'recent_events': recent_events,
        'available_moves': available_moves,
        'available_switches': available_switches,
        'is_forced_switch': is_forced_switch,
        'can_move': bool(ai_req.get('active')) and not ai_req.get('wait'),
        'must_wait': bool(ai_req.get('wait')),
        'side_conditions': side_data.get('sideConditions', {}),
        'field_conditions': field_conditions,
        'weather': weather,
        'terrain': terrain,
        'pseudoWeather': ai_req.get('pseudoWeather', [])
    }
    
    return observation

def _llm_agent_decision(observation: dict, team_knowledge: Optional[dict] = None) -> dict:
    """
    LLM agent that makes decisions based on battle observation.
    
    Args:
        observation: The battle state observation
        team_knowledge: Optional pre-battle team information
        
    Returns:
        Dictionary with 'action_type' ('move' or 'switch') and 'choice' (index or move name)
    """
    debug_print(f"LLM agent making decision. Forced switch: {observation.get('is_forced_switch', False)}", "LLM_AGENT")

    # Compose a prompt for the LLM agent that includes the new conditions
    prompt_context = (
        f"Turn: {observation.get('turn')}\n"
        f"Active Pokemon: {observation.get('active')}\n"
        f"Bench: {observation.get('bench')}\n"
        f"Opponent Active: {observation.get('opponent_active')}\n"
        f"Recent Events: {observation.get('recent_events')}\n"
        f"Available Moves: {observation.get('available_moves')}\n"
        f"Available Switches: {observation.get('available_switches')}\n"
        f"Is Forced Switch: {observation.get('is_forced_switch')}\n"
        f"Can Move: {observation.get('can_move')}\n"
        f"Must Wait: {observation.get('must_wait')}\n"
        f"Side Conditions: {observation.get('side_conditions')}\n"
        f"Field Conditions: {observation.get('field_conditions')}\n"
        f"Weather: {observation.get('weather')}\n"
        f"Terrain: {observation.get('terrain')}\n"
        f"PseudoWeather: {observation.get('pseudoWeather')}\n"
    )
    debug_print(f"LLM agent prompt context:\n{prompt_context}", "LLM_AGENT_PROMPT")

    # Handle forced switch scenarios
    if observation.get('is_forced_switch', False):
        available_switches = observation.get('available_switches', [])
        if available_switches:
            choice = available_switches[0]['index']
            debug_print(f"LLM agent chose forced switch: {choice}", "LLM_AGENT")
            return {
                'action_type': 'switch',
                'choice': choice,
                'reasoning': f"Forced to switch to {available_switches[0]['species']}"
            }
        else:
            debug_print("LLM agent: No switches available for forced switch", "LLM_AGENT")
            return {'action_type': 'switch', 'choice': 1, 'reasoning': 'No valid switches available'}

    # Handle wait scenarios (Pokemon can't move)
    if observation.get('must_wait', False):
        debug_print("LLM agent: Must wait, Pokemon cannot move", "LLM_AGENT")
        return {
            'action_type': 'wait',
            'choice': None,
            'reasoning': 'Pokemon cannot move this turn'
        }

    # Normal turn decision making
    available_moves = observation.get('available_moves', [])
    available_switches = observation.get('available_switches', [])

    # Try to use Gemini AI agent first
    try:
        if GEMINI_AVAILABLE:
            debug_print("Using Gemini AI agent for decision", "LLM_AGENT")
            decision = get_gemini_decision(observation, team_knowledge)
            return decision
        else:
            debug_print("Gemini not available, using heuristic fallback", "LLM_AGENT")
            raise ImportError("Gemini agent not available")

    except Exception as e:
        debug_print(f"LLM decision error: {e}, falling back to heuristic", "LLM_AGENT")
        # Fallback to simple logic if LLM fails
        if available_moves:
            # Simple heuristic: prefer moves with higher PP for sustainability
            best_move = None
            best_score = -1

            for move in available_moves:
                score = 0
                pp = move.get('pp', 0)
                max_pp = move.get('maxpp', 1)

                # Prefer moves with more PP remaining
                if max_pp > 0:
                    score += (pp / max_pp) * 10

                # Add some randomness for variety
                score += random.random() * 5

                if score > best_score:
                    best_score = score
                    best_move = move

            if best_move:
                debug_print(f"LLM agent chose move: {best_move['index']} ({best_move.get('move', 'unknown')})", "LLM_AGENT")
                return {
                    'action_type': 'move',
                    'choice': best_move['index'],
                    'reasoning': f"Selected {best_move.get('move', 'move')} (PP: {best_move.get('pp', '?')}/{best_move.get('maxpp', '?')})"
                }

        # If no moves available, try to switch
        if available_switches:
            # Simple switch logic - pick a random healthy Pokemon
            choice = random.choice(available_switches)
            debug_print(f"LLM agent chose switch: {choice['index']} ({choice['species']})", "LLM_AGENT")
            return {
                'action_type': 'switch',
                'choice': choice['index'],
                'reasoning': f"Switching to {choice['species']} ({choice['hp_status']})"
            }

    # Fallback - should rarely happen
    debug_print("LLM agent: No valid actions available", "LLM_AGENT")
    return {
        'action_type': 'move',
        'choice': 1,
        'reasoning': 'Fallback action - no valid options detected'
    }

def _translate_agent_decision(decision: dict, ai_req: dict) -> Optional[str]:
    """
    Translate LLM agent decision into simulator command.
    
    Args:
        decision: Decision from LLM agent
        ai_req: Current request from simulator
        
    Returns:
        Simulator command string or None if invalid
    """
    action_type = decision.get('action_type')
    choice = decision.get('choice')
    
    if action_type == 'wait' or choice is None:
        return None
    
    if action_type == 'switch':
        # Validate switch choice
        switches = _get_available_switches(ai_req)
        valid_indices = [s['index'] for s in switches]
        
        if choice in valid_indices:
            return f"switch {choice}"
        else:
            debug_print(f"Invalid switch choice {choice}, valid options: {valid_indices}", "TRANSLATION_ERROR")
            # Fallback to first available switch
            if valid_indices:
                return f"switch {valid_indices[0]}"
            return None
    
    elif action_type == 'move':
        # Validate move choice
        moves = _get_available_moves(ai_req)
        valid_indices = [m.get('original_index', i+1) for i, m in enumerate(moves)]
        
        if choice in valid_indices:
            return f"move {choice}"
        else:
            debug_print(f"Invalid move choice {choice}, valid options: {valid_indices}", "TRANSLATION_ERROR")
            # Fallback to first available move
            if valid_indices:
                return f"move {valid_indices[0]}"
            return None
    
    debug_print(f"Unknown action type: {action_type}", "TRANSLATION_ERROR")
    return None

def _parse_team_knowledge(team_content: str, side: str = "p2") -> dict:
    """
    Parse team file content to provide pre-battle knowledge to the LLM agent.
    
    Args:
        team_content: Raw team file content (Showdown importable format)
        side: Which side this team belongs to ("p1" or "p2")
        
    Returns:
        Dictionary containing team knowledge
    """
    team_knowledge = {
        'side': side,
        'pokemon': [],
        'format_info': {},
        'raw_content': team_content
    }
    
    if not team_content:
        return team_knowledge
    
    try:
        # Split by Pokemon (each Pokemon starts with a line that doesn't begin with whitespace)
        lines = team_content.strip().split('\n')
        current_pokemon = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # New Pokemon (line doesn't start with dash or whitespace in original)
            if not line.startswith('-') and not line.startswith('@') and not line.startswith('Ability:') and not line.startswith('EVs:') and not line.startswith('IVs:') and not line.startswith('Nature:') and '@' in line:
                if current_pokemon:
                    team_knowledge['pokemon'].append(current_pokemon)
                
                # Parse pokemon name and item
                if ' @ ' in line:
                    name_part, item = line.split(' @ ', 1)
                else:
                    name_part = line
                    item = None
                
                current_pokemon = {
                    'name': name_part.strip(),
                    'item': item.strip() if item else None,
                    'ability': None,
                    'moves': [],
                    'nature': None,
                    'evs': {},
                    'ivs': {},
                    'level': 50  # Default level
                }
            
            elif current_pokemon:
                # Parse Pokemon details
                if line.startswith('Ability:'):
                    current_pokemon['ability'] = line.replace('Ability:', '').strip()
                elif line.startswith('EVs:'):
                    ev_part = line.replace('EVs:', '').strip()
                    # Parse EVs like "252 HP / 252 Atk / 4 SpD"
                    for ev_stat in ev_part.split(' / '):
                        if ' ' in ev_stat:
                            value, stat = ev_stat.strip().split(' ', 1)
                            try:
                                current_pokemon['evs'][stat] = int(value)
                            except ValueError:
                                pass
                elif line.startswith('IVs:'):
                    iv_part = line.replace('IVs:', '').strip()
                    # Parse IVs similar to EVs
                    for iv_stat in iv_part.split(' / '):
                        if ' ' in iv_stat:
                            value, stat = iv_stat.strip().split(' ', 1)
                            try:
                                current_pokemon['ivs'][stat] = int(value)
                            except ValueError:
                                pass
                elif line.endswith(' Nature'):
                    current_pokemon['nature'] = line.replace(' Nature', '').strip()
                elif line.startswith('- '):
                    # Move
                    move = line.replace('- ', '').strip()
                    current_pokemon['moves'].append(move)
        
        # Add the last Pokemon
        if current_pokemon:
            team_knowledge['pokemon'].append(current_pokemon)
            
        debug_print(f"Parsed team knowledge for {side}: {len(team_knowledge['pokemon'])} Pokemon", "TEAM_KNOWLEDGE")
        
    except Exception as e:
        debug_print(f"Error parsing team knowledge: {e}", "TEAM_KNOWLEDGE_ERROR")
    
    return team_knowledge

def _show_pokemon_showdown_menu(req: dict, battle: Dict[str, BattleSide], active_side: str, ui: Optional[GameWindow] = None) -> str:
    """Display Pokemon Showdown style menu and get user choice."""
    # In UI mode, move cursor below the window for clean menu display
    if ui and ui.enabled:
        # Move cursor well below the window
        sys.stdout.write(_ansi(f'{ui.feed_lines + 10}H'))  # Move to line well below window
        sys.stdout.flush()
    
    # Clear/space and hint the window is updating – do not reprint overlay in window mode
    print("\n" + "="*50)
    if not (ui and ui.enabled):
        # In non-window mode, also show the overlay
        print(_render_overlay(battle))
    
    # Get the active Pokemon name
    active_pokemon = battle[active_side].get('name', 'Pokemon')
    
    # Check if this is a forced switch
    force_switch = req.get('forceSwitch') or [False]
    if force_switch[0]:
        # Check if the active Pokemon is fainted
        side = req.get('side', {})
        pokemon_list = side.get('pokemon', [])
        active_pokemon_fainted = False
        active_pokemon_index = None
        
        for i, pokemon in enumerate(pokemon_list, start=1):
            if pokemon.get('active', False):
                active_pokemon_index = i
                condition = pokemon.get('condition', '')
                if 'fnt' in condition:
                    active_pokemon_fainted = True
                break
        
        if active_pokemon_fainted:
            print(f"\n{active_pokemon} fainted!")
        else:
            print(f"\n{active_pokemon} must switch out!")
        
        print("Choose a Pokemon to send out:")
        switches = _get_available_switches(req)
        
        # If this is a pivot switch (not due to fainting), exclude the active Pokemon
        valid_switches = []
        display_num = 1
        for switch in switches:
            # Skip the currently active Pokemon if it's not fainted
            if not active_pokemon_fainted and switch['index'] == active_pokemon_index:
                continue
            details = switch['pokemon'].get('details', '')
            condition = switch['pokemon'].get('condition', '')
            print(f"  {display_num}. {details} [{condition}]")
            valid_switches.append(switch)
            display_num += 1
        
        if not valid_switches:
            print("No other Pokemon available to switch to!")
            return "pass"  # This shouldn't happen in normal gameplay
        
        while True:
            try:
                choice = input(f"\nSelect Pokemon (1-{len(valid_switches)}): ").strip()
                choice_num = int(choice)
                if 1 <= choice_num <= len(valid_switches):
                    switch_index = valid_switches[choice_num - 1]['index']
                    return f"switch {switch_index}"
                else:
                    print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a number.")
            except KeyboardInterrupt:
                raise  # Re-raise to handle gracefully in main loop
    
    # Normal turn menu
    while True:
        try:
            print(f"\nWhat will {active_pokemon} do?")
            print("  1. Fight")
            print("  2. Pokemon")
            main_choice = input("\nChoose an option: ").strip()
            
            if main_choice == "1":  # Fight
                moves = _get_available_moves(req)
                if not moves:
                    print("No moves available!")
                    continue
                
                print(f"\n{active_pokemon}'s moves:")
                for i, move in enumerate(moves, 1):
                    name = move.get('move') or move.get('id') or f"move{i}"
                    pp_info = f"({move.get('pp','?')}/{move.get('maxpp','?')})"
                    target_info = f" -> {move['target']}" if move.get('target') else ""
                    print(f"  {i}. {name} {pp_info}{target_info}")
                
                while True:
                    try:
                        move_choice = input(f"\nSelect move (1-{len(moves)} or 'back'): ").strip()
                        if move_choice.lower() == 'back':
                            break
                        move_num = int(move_choice)
                        if 1 <= move_num <= len(moves):
                            # Use the original index from the move data
                            selected_move = moves[move_num - 1]
                            original_index = selected_move.get('original_index', move_num)
                            return f"move {original_index}"
                        else:
                            print("Invalid move choice.")
                    except ValueError:
                        print("Please enter a number or 'back'.")
                    except (EOFError, KeyboardInterrupt):
                        raise  # Re-raise to handle gracefully in main loop
                    except Exception as e:
                        print(f"Unexpected input error: {e}")
                        debug_print(f"Move selection error: {e}", "MENU_ERROR")
            
            elif main_choice == "2":  # Pokemon
                switches = _get_available_switches(req)
                if len(switches) <= 1:  # Only current Pokemon available
                    print("No other Pokemon available to switch to!")
                    continue
                
                print(f"\nChoose a Pokemon:")
                valid_switches = []
                display_num = 1
                
                # Find the active Pokemon to exclude it
                active_pokemon_index = None
                side = req.get('side', {})
                pokemon_list = side.get('pokemon', [])
                for i, pokemon in enumerate(pokemon_list, start=1):
                    if pokemon.get('active', False):
                        active_pokemon_index = i
                        break
                
                for switch in switches:
                    # Skip the currently active Pokemon
                    if switch['index'] == active_pokemon_index:
                        continue
                    details = switch['pokemon'].get('details', '')
                    condition = switch['pokemon'].get('condition', '')
                    print(f"  {display_num}. {details} [{condition}]")
                    valid_switches.append(switch)
                    display_num += 1
                
                if not valid_switches:
                    print("No other Pokemon available to switch to!")
                    continue
                
                while True:
                    try:
                        switch_choice = input(f"\nSelect Pokemon (1-{len(valid_switches)} or 'back'): ").strip()
                        if switch_choice.lower() == 'back':
                            break
                        switch_num = int(switch_choice)
                        if 1 <= switch_num <= len(valid_switches):
                            switch_index = valid_switches[switch_num - 1]['index']
                            return f"switch {switch_index}"
                        else:
                            print("Invalid Pokemon choice.")
                    except ValueError:
                        print("Please enter a number or 'back'.")
                    except (EOFError, KeyboardInterrupt):
                        raise  # Re-raise to handle gracefully in main loop
                    except Exception as e:
                        print(f"Unexpected input error: {e}")
                        debug_print(f"Switch selection error: {e}", "MENU_ERROR")
            else:
                print("Invalid choice. Please enter 1 or 2.")
            
        except (ValueError, KeyboardInterrupt):
            raise  # Re-raise KeyboardInterrupt to handle gracefully in main loop

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("p1", nargs='?', default=None, help="Path to Player 1 team file (Showdown importable)")
    parser.add_argument("p2", nargs='?', default=None, help="Path to Player 2 team file")
    parser.add_argument("--format", default="gen7ou")
    parser.add_argument("--randbat", action="store_true", help="Enable random battles, generating teams automatically.")
    parser.add_argument("--no-auto-preview", action="store_true",
                        help="Do not auto-pick team preview; prompt for order")
    parser.add_argument("--side", choices=["p1", "p2"], default="p1",
                        help="Control this side by default (unprefixed commands)")
    parser.add_argument("--p2-ai", dest="p2_ai", action="store_true",
                        help="Make player 2 act automatically with random choices (default)")
    parser.add_argument("--no-p2-ai", dest="p2_ai", action="store_false",
                        help="Disable player 2 AI")
    parser.add_argument("--humanize", dest="humanize", action="store_true",
                        help="Show a terse humanized feed (summarized events)")
    parser.add_argument("--raw", dest="humanize", action="store_false",
                        help="Show raw simulator stream lines")
    parser.add_argument("--window", dest="window", action="store_true",
                        help="Render an in-terminal game window (default)")
    parser.add_argument("--no-window", dest="window", action="store_false",
                        help="Disable the in-terminal game window")
    parser.add_argument("--debug", action="store_true", help="Enable debug printing.")
    parser.set_defaults(p2_ai=True, humanize=True, window=True)
    args = parser.parse_args()

    if args.debug:
        showdown_wrapper.DEBUG = True
    
    debug_print("Starting improved CLI battle interface", "MAIN")
    debug_print(f"Command line args parsed: {args}", "MAIN")
    
    # Initialize Gemini agent if available and API key is set
    if GEMINI_AVAILABLE and args.p2_ai:
        try:
            # Try to initialize Gemini agent
            import os
            api_key = os.getenv('GOOGLE_AI_API_KEY') or os.getenv('GEMINI_API_KEY')
            if api_key:
                init_gemini_agent(api_key)
                debug_print("Gemini AI agent initialized successfully", "MAIN")
            else:
                debug_print("No API key found for Gemini. Set GOOGLE_AI_API_KEY environment variable to use AI agent", "MAIN")
        except Exception as e:
            debug_print(f"Failed to initialize Gemini agent: {e}", "MAIN")

    # Validate arguments
    if not args.randbat and (not args.p1 or not args.p2):
        parser.error(
            "Error: p1 and p2 team file arguments are required unless --randbat is specified.\n"
            "Example usage for random battles:\n"
            "  python cli.py --randbat --format gen7randombattle\n"
            "Or for custom teams:\n"
            "  python cli.py path/to/p1.txt path/to/p2.txt"
        )

    # Determine format for random battles
    battle_format = args.format
    if args.randbat:
        # if args.format == 'gen7ou':  # If default format is unchanged, switch to random
        #     battle_format = 'gen7randombattle'
        debug_print(f"Random battle enabled. Using format: {battle_format}", "MAIN")
    else:
        debug_print(f"Using specified format: {battle_format}", "MAIN")
   
    # Pack teams or generate for randbat
    try:
        if args.randbat:
            print("Generating and validating random teams...")
            p1_team = showdown_wrapper.generate_random_team(formatid=battle_format)
            p2_team = showdown_wrapper.generate_random_team(formatid=battle_format)
            if not p1_team or not p2_team:
                raise RuntimeError("Failed to generate random teams.")
            debug_print(f"Random teams generated for format {battle_format}", "TEAMS")
            # For random battles, we don't have team file content to parse
            team_knowledge = None
        else:
            print(f"Packing and validating teams... for {battle_format}")
            # Read team file content for P2 (AI side) before packing
            with open(args.p2, 'r', encoding='utf-8') as f:
                p2_team_content = f.read()
            
            p1_team = pack_team(args.p1, battle_format)
            p2_team = pack_team(args.p2, battle_format)
            debug_print(f"P1 team packed length: {len(p1_team)}, P2 team packed length: {len(p2_team)}", "TEAMS")
            
            # Parse team knowledge for the AI (P2)
            team_knowledge = _parse_team_knowledge(p2_team_content, "p2")
            debug_print(f"Team knowledge parsed for P2: {len(team_knowledge.get('pokemon', []))} Pokemon", "TEAMS")
    except RuntimeError as e:
        print(f"Error: {e}")
        print("Please check that Node.js is installed and team files are valid.")
        return
    except Exception as e:
        print(f"Unexpected error preparing teams: {e}")
        debug_print(f"Unexpected team preparation error: {e}", "TEAMS_ERROR")
        return

    debug_print("Initializing Pokemon Showdown simulator...", "SIMULATOR")
    try:
        sim = ShowdownWrapper(formatid=battle_format)
        sim.send(f'>player p1 {{"name":"P1","team":"{p1_team}"}}')
        sim.send(f'>player p2 {{"name":"P2","team":"{p2_team}"}}')
        debug_print("Simulator initialized and teams sent", "SIMULATOR")
    except Exception as e:
        print(f"Error initializing simulator: {e}")
        debug_print(f"Simulator initialization error: {e}", "SIMULATOR_ERROR")
        return

    # Track current request state for each side
    requests: Dict[str, dict] = {}
    # Track last shown request id to avoid spamming
    shown_rqid: Dict[str, Optional[int]] = {"p1": None, "p2": None}
    ai_error_count = {'p2': 0}  # Track AI errors to prevent infinite loops
    max_ai_errors = 3  # Maximum errors before forcing different action
    ai_loop_counter = 0  # Track consecutive AI attempts without simulator response
    max_ai_loops = 15   # Prevent infinite loops
    preview_done = set()
    battle = _new_battle_state()
    current_turn = 0  # Track current turn for LLM agent context
    # team_knowledge will be set during team preparation

    # Setup UI window
    ui = GameWindow(enabled=args.window and sys.stdout.isatty())
    ui.mount()
    ui.add_feed("Battle started! Welcome to CLI-Mon Showdown!")
    ui.render(battle)
    humanize_mode = args.humanize
    debug_print("Entering main battle loop", "MAIN")

    try:
        while True:
            # Wait for and process simulator output
            out = sim.wait_for_output(timeout=1.0)
            debug_print(f"Simulator output: {len(out) if out else 0} lines", "SIMULATOR")
            if out:
                ai_loop_counter = 0  # Reset counter when we get simulator output
                result = _process_output(out, humanize_mode, args.side, requests, shown_rqid, battle, ai_error_count, current_turn, ui)
                # Handle the updated return value (winner, player_error_detected, current_turn)
                if isinstance(result, tuple) and len(result) == 3:
                    winner, player_error_detected, current_turn = result
                elif isinstance(result, tuple) and len(result) == 2:
                    # Backward compatibility if old return format is used
                    winner, player_error_detected = result
                else:
                    # Even more backward compatibility
                    winner = result
                    player_error_detected = False
                
                debug_print(f"Process output result - Winner: {winner}, Error: {player_error_detected}", "MAIN")
                if winner:
                    msg = f"🎉 Battle over! Winner: {winner} 🎉"
                    if ui and ui.enabled:
                        ui.add_feed(msg)
                        ui.render(battle)
                    else:
                        print(f"\n{msg}")
                    return
                
                # Check for double KO scenario
                p1_fainted = battle.get('p1', {}).get('fainted', False)
                p2_fainted = battle.get('p2', {}).get('fainted', False)
                if p1_fainted and p2_fainted:
                    # This is a potential double KO. Check if the game is about to end or if players can switch.
                    p1_req = requests.get('p1', {})
                    p2_req = requests.get('p2', {})

                    # Check if players have non-fainted pokemon to switch to
                    p1_can_switch = any(not p.get('condition', '').endswith('fnt') for p in p1_req.get('side', {}).get('pokemon', []) if not p.get('active'))
                    p2_can_switch = any(not p.get('condition', '').endswith('fnt') for p in p2_req.get('side', {}).get('pokemon', []) if not p.get('active'))

                    # If both active pokemon are fainted and at least one player has no pokemon left, it's a loss/tie.
                    if not p1_can_switch or not p2_can_switch:
                         debug_print("Double KO detected, but one player has no remaining Pokemon. Game should end.", "MAIN")
                    else:
                        if p1_can_switch and p2_can_switch:
                            # Both sides have replacement options after a double KO.
                            # Proactively handle the human side's forced switch here so the AI
                            # can also choose in the same iteration below.
                            try:
                                human_side = args.side
                                human_req = requests.get(human_side)
                                # Only act if we actually have a forceSwitch-style request
                                if human_req and (human_req.get('forceSwitch') or [False])[0]:
                                    # Compute a stable rqid like in the normal handling path
                                    player_rqid = human_req.get('rqid')
                                    if player_rqid is None:
                                        player_rqid = hash(
                                            str(human_req.get('_seq')) +
                                            '|' + str(human_req.get('active')) +
                                            '|' + str(human_req.get('forceSwitch'))
                                        )
                                    if shown_rqid.get(human_side) != player_rqid:
                                        # Prompt and send the human switch immediately
                                        choice = _show_pokemon_showdown_menu(human_req, battle, human_side, ui)
                                        sim.send(f">{human_side} {choice}")
                                        note = f"[sent] {human_side} {choice}"
                                        if ui and ui.enabled:
                                            ui.add_feed(note)
                                            ui.render(battle)
                                        else:
                                            print(f"\n{note}")
                                        shown_rqid[human_side] = player_rqid
                            except (KeyboardInterrupt, EOFError):
                                print("\n\nBattle interrupted by user during switch selection")
                                return
                            except Exception as e:
                                debug_print(f"Error handling double-KO switch prompt: {e}", "MAIN")

                        # Both players have fainted active pokemon but also have pokemon to switch to. This is the problematic state.
                        #raise Exception("Double KO detected: Both active Pokemon fainted simultaneously.")
                
                # If a player error was detected, force a short wait to get updated requests
                if player_error_detected:
                    debug_print("Player error detected, waiting for updated requests", "ERROR_RECOVERY")
                    time.sleep(0.2)  # Brief wait for simulator to send updated request
                    # Get any additional output that might contain updated requests
                    additional_out = sim.wait_for_output(timeout=0.5)
                    if additional_out:
                        debug_print(f"Got additional output after error: {len(additional_out)} lines", "ERROR_RECOVERY")
                        _parse_stream_lines(additional_out, requests)  # Update requests

                # Auto-handle team preview if required
                debug_print(f"Checking team preview auto-handling...", "PREVIEW")
                for side in ("p1", "p2"):
                    req = requests.get(side)
                    debug_print(f"Side {side} request: {bool(req)}, has teamPreview: {bool(req and req.get('teamPreview'))}, preview_done: {side in preview_done}", "PREVIEW")
                    if req and req.get("teamPreview") and side not in preview_done:
                        team = (req.get("side") or {}).get("pokemon") or []
                        n = len(team) if team else 0
                        debug_print(f"Side {side} team preview: {n} Pokemon", "PREVIEW")
                        if n:
                            default_order = ",".join(str(i) for i in range(1, n + 1))
                            debug_print(f"Default team order for {side}: {default_order}", "PREVIEW")
                            sim.send(f">{side} team {default_order}")
                            preview_done.add(side)
                            note = f"[auto] Team preview completed for {side}"
                            if ui and ui.enabled:
                                ui.add_feed(note)
                                ui.render(battle)
                            else:
                                print(note)
                            debug_print(f"Auto team preview sent for {side}: {default_order}", "PREVIEW")
                            continue  # Continue to process response immediately
            else:
                debug_print("No simulator output received", "SIMULATOR")
                # Increment AI loop counter when no output is received
                if args.p2_ai:
                    ai_loop_counter += 1
                    ai_error_count['p2'] += 1  # Increment error count as well
                    debug_print(f"AI loop counter incremented to {ai_loop_counter}", "AI")
                    if ai_loop_counter >= max_ai_loops:
                        raise Exception("AI appears stuck in a loop without simulator response.")   
                time.sleep(0.1)  # Prevent busy waiting
            # Handle AI for P2 - use LLM agent instead of random choices
            if args.p2_ai:
                ai_req = requests.get('p2')
                debug_print(f"P2 AI check - Has request: {bool(ai_req)}", "AI")
                if ai_req:
                    ai_rqid = ai_req.get('rqid')
                    if ai_rqid is None:
                        # Use our per-side sequence to force progress even if rqid is missing/unchanged
                        ai_rqid = hash(
                            str(ai_req.get('_seq')) +
                            '|' + str(ai_req.get('active')) +
                            '|' + str(ai_req.get('forceSwitch')) +
                            '|' + str(ai_req.get('wait'))
                        )
                    debug_print(f"P2 AI request ID: {ai_rqid}, last shown: {shown_rqid.get('p2')}", "AI")
                    
                    # Special handling for forced switches - always process them even if request ID is the same
                    # because consecutive KOs can generate the same request ID
                    force_switch = (ai_req.get('forceSwitch') or [False])[0]
                    
                    if force_switch or shown_rqid.get('p2') != ai_rqid:
                        # Create observation for LLM agent
                        observation = _create_agent_observation(ai_req, battle, ui, current_turn)
                        debug_print(f"Created observation for LLM agent: turn {current_turn}", "LLM_AGENT")
                        
                        # Handle wait requests first (Pokemon can't move)
                        if ai_req.get('wait') or ai_req.get('cant'):
                            debug_print("P2 AI has wait request - Pokemon can't move", "AI")
                            note = f"[p2-ai] Pokemon can't move"
                            if ui and ui.enabled:
                                ui.add_feed(note)
                                ui.render(battle)
                            else:
                                print(note)
                            shown_rqid['p2'] = ai_rqid
                            continue
                        
                        # Get decision from LLM agent
                        try:
                            decision = _llm_agent_decision(observation, team_knowledge)
                            debug_print(f"LLM agent decision: {decision}", "LLM_AGENT")
                            
                            # Translate decision to simulator command
                            command = _translate_agent_decision(decision, ai_req)
                            
                            if command:
                                sim.send(f">p2 {command}")
                                reasoning = decision.get('reasoning', 'No reasoning provided')
                                note = f"[p2-ai] {command} ({reasoning})"
                                if ui and ui.enabled:
                                    ui.add_feed(note)
                                    #ui.render(battle)
                                else:
                                    print(note)
                                debug_print(f"P2 AI sent command: {command}", "AI")
                                shown_rqid['p2'] = ai_rqid
                                ai_loop_counter = 0  # Reset counter on successful action
                                ai_error_count['p2'] = 0  # Reset error count on successful action
                                continue
                            else:
                                debug_print("LLM agent failed to generate valid command", "AI")
                                ai_error_count['p2'] += 1
                        
                        except Exception as e:
                            debug_print(f"LLM agent error: {e}", "AI_ERROR")
                            ai_error_count['p2'] += 1
                        
                        # Fallback for errors - try to handle basic cases
                        if ai_error_count.get('p2', 0) >= max_ai_errors:
                            debug_print("Too many AI errors, using fallback logic", "AI")
                            
                            # Handle forced switch as fallback
                            if (ai_req.get('forceSwitch') or [False])[0]:
                                switches = _get_forced_switch_options(ai_req)
                                if switches:
                                    choice = switches[0]['index']
                                    sim.send(f">p2 switch {choice}")
                                    note = f"[p2-ai] switch {choice} (fallback)"
                                    if ui and ui.enabled:
                                        ui.add_feed(note)
                                        ui.render(battle)
                                    else:
                                        print(note)
                                    debug_print(f"P2 AI fallback switch: {choice}", "AI")
                                    shown_rqid['p2'] = ai_rqid
                                    ai_error_count['p2'] = 0
                                    continue
                                else:
                                    # Check if this is end of game scenario
                                    all_fainted = all(poke.get('condition', '').endswith('fnt') 
                                                    for poke in ai_req.get('side', {}).get('pokemon', []))
                                    if all_fainted:
                                        debug_print("P2 AI: All Pokemon fainted - game should end", "AI")
                                        sim.send(">p2 forfeit")
                                        debug_print("P2 AI: Sent forfeit due to no available Pokemon", "AI")
                                    shown_rqid['p2'] = ai_rqid
                                    break
                            
                            # Handle moves as fallback
                            elif ai_req.get('active'):
                                moves = _get_available_moves(ai_req)
                                if moves:
                                    active = ai_req['active'][0]
                                    all_moves = active.get('moves', [])
                                    available_indices = []
                                    for i, move in enumerate(all_moves, start=1):
                                        if not move.get('disabled'):
                                            available_indices.append(i)
                                    
                                    if available_indices:
                                        pick = random.choice(available_indices)
                                        sim.send(f">p2 move {pick}")
                                        note = f"[p2-ai] move {pick} (fallback)"
                                        if ui and ui.enabled:
                                            ui.add_feed(note)
                                            ui.render(battle)
                                        else:
                                            print(note)
                                        debug_print(f"P2 AI fallback move: {pick}", "AI")
                                        shown_rqid['p2'] = ai_rqid
                                        ai_error_count['p2'] = 0
                                        continue

            # AI loop detection - prevent infinite loops when simulator doesn't respond
            if args.p2_ai and requests.get('p2'):
                ai_loop_counter += 1
                debug_print(f"AI loop counter: {ai_loop_counter}/{max_ai_loops}", "AI")
                if ai_loop_counter >= max_ai_loops:
                    debug_print("AI loop limit reached - simulator not responding, ending battle", "AI")
                    if ui and ui.enabled:
                        ui.add_feed("Battle ended due to technical issues")
                        ui.render(battle)
                    break

            # Check if we need player input
            player_req = requests.get(args.side)
            if player_req:
                # Handle "wait": true requests (Pokemon can't move due to paralysis, flinch, etc.)
                if player_req.get('wait'):
                    player_rqid = player_req.get('rqid')
                    if player_rqid is None:
                        player_rqid = hash(str(player_req.get('_seq')) + '|' + str(player_req.get('wait')))
                    
                    if shown_rqid.get(args.side) != player_rqid:
                        debug_print(f"Player {args.side} has wait request - Pokemon can't move", "WAIT")
                        note = f"[wait] {args.side} Pokemon can't move"
                        if ui and ui.enabled:
                            ui.add_feed(note)
                            ui.render(battle)
                        else:
                            print(f"\n{note}")
                        shown_rqid[args.side] = player_rqid
                        # After handling a wait request, immediately check for new output
                        # This helps catch any pending forced switches for the AI
                        additional_out = sim.wait_for_output(timeout=0.1)
                        if additional_out:
                            debug_print(f"Got additional output after wait: {len(additional_out)} lines", "WAIT_RECOVERY")
                            _parse_stream_lines(additional_out, requests)
                        continue
                
                # Handle normal requests (active moves or forced switches)
                elif player_req.get('active') or player_req.get('forceSwitch'):
                    player_rqid = player_req.get('rqid')
                    if player_rqid is None:
                        player_rqid = hash(
                            str(player_req.get('_seq')) +
                            '|' + str(player_req.get('active')) +
                            '|' + str(player_req.get('forceSwitch'))
                        )
                    
                    if shown_rqid.get(args.side) != player_rqid:
                        # Show Pokemon Showdown style menu and get choice
                        try:
                            choice = _show_pokemon_showdown_menu(player_req, battle, args.side, ui)
                            sim.send(f">{args.side} {choice}")
                            note = f"[sent] {args.side} {choice}"
                            if ui and ui.enabled:
                                ui.add_feed(note)
                                ui.render(battle)
                            else:
                                print(f"\n{note}")
                            shown_rqid[args.side] = player_rqid
                            continue  # Continue to process response immediately
                        except KeyboardInterrupt:
                            print("\n\nExiting battle...")
                            break
                        except (EOFError, KeyboardInterrupt):
                            print("\n\nBattle interrupted by user")
                            break
                        except ValueError as e:
                            print(f"Invalid input: {e}")
                            debug_print(f"Menu input error: {e}", "MENU_ERROR")
                            # Continue to allow retry
                        except Exception as e:
                            print(f"Unexpected error in menu: {e}")
                            debug_print(f"Unexpected menu error: {e}", "MENU_ERROR")
                            break
            
            # If no one needs to act, wait a bit to avoid busy loop
            if not out:
                time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\nBattle interrupted by user")
        debug_print("Battle interrupted by user (Ctrl+C)", "MAIN")
    except (ConnectionError, OSError) as e:
        print(f"\nConnection error with simulator: {e}")
        debug_print(f"Simulator connection error: {e}", "MAIN_ERROR")
    except Exception as e:
        print(f"\nUnexpected error during battle: {e}")
        debug_print(f"Unexpected main loop error: {e}", "MAIN_ERROR")
        import traceback
        debug_print(f"Full traceback: {traceback.format_exc()}", "MAIN_ERROR")
    finally:
        try:
            sim.close()
            debug_print("Simulator closed successfully", "MAIN")
        except Exception as e:
            debug_print(f"Error closing simulator: {e}", "MAIN_ERROR")


if __name__ == "__main__":
    main()
