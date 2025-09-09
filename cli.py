import argparse
import json
import subprocess
import random
from typing import Dict, Optional, Tuple
from showdown_wrapper import ShowdownWrapper

# Debug flag - set to True to enable detailed debugging
DEBUG = False

def debug_print(msg: str, prefix: str = "DEBUG"):
    """Print debug messages if debugging is enabled"""
    if DEBUG:
        print(f"[{prefix}] {msg}")

# ---- Lightweight 1v1 battle state for reactive UI ----
BattleSide = Dict[str, Optional[object]]  # name, hp, maxhp, status, fainted

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
    # returns (hp, maxhp, hp_pct, fainted)
    tok = tok.strip()
    if 'fnt' in tok:
        return 0, None, 0, True
    if '/' in tok:
        try:
            cur, maximum = tok.split('/', 1)
            cur_i = int(cur)
            max_i = int(maximum)
            pct = int(round((cur_i / max_i) * 100)) if max_i else None
            return cur_i, max_i, pct, False
        except Exception:
            return None, None, None, False
    return None, None, None, False

def _update_battle_state_from_line(line: str, battle: Dict[str, BattleSide]) -> bool:
    debug_print(f"Processing battle line: {line.strip()}", "BATTLE_STATE")
    changed = False
    if not line or '|' not in line:
        return False
    parts = line.strip().split('|')
    # parts[0] is '' usually for battle messages
    if len(parts) < 2:
        return False
    tag = parts[1]
    debug_print(f"Battle tag: {tag}, parts: {len(parts)}", "BATTLE_STATE")
    if tag in ('switch', 'drag') and len(parts) >= 3:
        side, name = _parse_actor(parts[2])
        debug_print(f"Pokemon switch/drag - Side: {side}, Name: {name}", "BATTLE_STATE")
        if side in battle and name:
            if battle[side].get('name') != name:
                battle[side]['name'] = name
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
                    if hp is not None and battle[side].get('hp') != hp:
                        battle[side]['hp'] = hp
                        changed = True
                    if maxhp is not None and battle[side].get('maxhp') != maxhp:
                        battle[side]['maxhp'] = maxhp
                        changed = True
                    if hp_pct is not None and battle[side].get('hp_pct') != hp_pct:
                        battle[side]['hp_pct'] = hp_pct
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
                # Handle percentage-style reports like 91/100
                if maxhp == 100 and known_max and known_max != 100:
                    # convert percent to absolute
                    abs_hp = int(round((hp or 0) * known_max / 100))
                    if battle[side].get('hp') != abs_hp:
                        battle[side]['hp'] = abs_hp
                        changed = True
                    # keep maxhp as known_max
                else:
                    if hp is not None and battle[side].get('hp') != hp:
                        battle[side]['hp'] = hp
                        changed = True
                    if maxhp is not None and battle[side].get('maxhp') != maxhp:
                        battle[side]['maxhp'] = maxhp
                        changed = True
                # Always track hp_pct if available
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
    return changed

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
        return f"{name}: {hp}"
    if tag == 'faint' and len(parts) >= 3:
        _, name = _parse_actor(parts[2])
        return f"{name} fainted!"
    if tag == 'switch' and len(parts) >= 3:
        side, name = _parse_actor(parts[2])
        return f"{_side_label(side)} sent out {name}"
    if tag == '-boost' and len(parts) >= 5:
        side, name = _parse_actor(parts[2])
        stat = parts[3]
        amount = parts[4]
        return f"{name}'s {stat} rose by {amount}!"
    if tag == '-unboost' and len(parts) >= 5:
        side, name = _parse_actor(parts[2])
        stat = parts[3]
        amount = parts[4]
        return f"{name}'s {stat} fell by {amount}."
    if tag == '-status' and len(parts) >= 4:
        side, name = _parse_actor(parts[2])
        status = parts[3]
        return f"{name} is {status}."
    if tag == '-curestatus' and len(parts) >= 4:
        side, name = _parse_actor(parts[2])
        status = parts[3]
        return f"{name} was cured of {status}."
    if tag == '-start' and len(parts) >= 4:
        side, name = _parse_actor(parts[2])
        what = parts[3]
        if what == 'typechange' and len(parts) >= 5:
            return f"{name} became {parts[4]}"
        return f"{name} started {what}"
    if tag == 'upkeep':
        return None
    if tag == 'win' and len(parts) >= 3:
        return f"Winner: {parts[2]}"
    return None

def _process_output(out_lines, humanize: bool, active_side: str, requests: Dict[str, dict], shown_rqid: Dict[str, Optional[int]], battle: Dict[str, BattleSide]) -> Optional[str]:
    if not out_lines:
        return None
    winner: Optional[str] = None
    overlay_changed = False
    
    # Parse requests from the entire stream first
    debug_print(f"Parsing stream for requests from {len(out_lines)} lines", "REQUESTS")
    _parse_stream_lines(out_lines, requests)
    debug_print(f"Requests after parsing: {list(requests.keys())}", "REQUESTS")
    
    for line in out_lines:
        # Print
        if humanize:
            msg = _humanize_line(line)
            if msg:
                print(msg)
        else:
            print(line, end='')
        # State update
        try:
            if _update_battle_state_from_line(line, battle):
                overlay_changed = True
        except Exception:
            pass
        # Winner
        if '|win|' in line:
            winner = line.split('|win|', 1)[1].strip() or 'Unknown'
    # Overlay
    if overlay_changed:
        print(_render_overlay(battle))
    # Show prompt for new request on active side
    active_req = requests.get(active_side)
    if active_req:
        rqid = active_req.get('rqid')
        if rqid is None:
            rqid = hash(str(active_req.get('active')) + str(active_req.get('forceSwitch')) + str(active_req.get('teamPreview')))
        if shown_rqid.get(active_side) != rqid:
            if active_req.get('teamPreview'):
                print("\n[Your team preview is requested] Type: team N,...\n")
            elif active_req.get('active'):
                print("\n[Your move is requested] Available moves:")
                print(_pretty_moves(active_req))
                print("\nType: move N  or  switch N  (or 'moves'/'switches' to display again)\n")
            shown_rqid[active_side] = rqid
    return winner

def pack_team(path: str) -> str:
    result = subprocess.run(
        ["node", "teamutils.js", path],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip()


def _pretty_moves(req: dict) -> str:
    if req and req.get('teamPreview'):
        return "Team preview in progress. Use 'team N,...' to set order."
    if not req or 'active' not in req or not req['active']:
        return "No move request available."
    active = req['active'][0]
    if active.get('trapped'):
        trapped = ' [trapped]'
    else:
        trapped = ''
    out = []
    moves = active.get('moves', [])
    for i, m in enumerate(moves, start=1):
        name = m.get('move') or m.get('id') or f"move{i}"
        desc = f"{i}. {name} ({m.get('pp','?')}/{m.get('maxpp','?')})"
        if m.get('disabled'):
            desc += " [disabled]"
        if m.get('target'):
            desc += f" -> {m['target']}"
        out.append(desc)
    flags = []
    if active.get('canMegaEvo'):
        flags.append('mega')
    if active.get('canZMove'):
        flags.append('zmove')
    if active.get('canDynamax'):
        flags.append('dmax')
    if active.get('canGigantamax'):
        flags.append('gmax')
    if active.get('canTerastallize'):
        flags.append('tera')
    if flags:
        out.append("Options: " + ", ".join(flags))
    if trapped:
        out.append(trapped)
    return "\n".join(out) or "No moves available."


def _pretty_switches(req: dict) -> str:
    if not req:
        return "No switch request available."
    force = req.get('forceSwitch') or [False]
    if not force[0] and not req.get('teamPreview'):
        return "Switch not requested."
    side = req.get('side') or {}
    pokemon = side.get('pokemon') or []
    out = []
    for i, p in enumerate(pokemon, start=1):
        details = p.get('details', '')
        condition = p.get('condition', '')
        # Skip fainted
        if 'fnt' in condition:
            continue
        out.append(f"{i}. {details} [{condition}]")
    return "\n".join(out) or "No switchable Pokémon."


def _help_text(active_side: str = "p1") -> str:
    return (
        "Commands (1v1 friendly):\n"
        "  move N [mega|zmove|dmax|gmax|tera]  - choose a move for your side (also: N, mN, moveN)\n"
        "  switch N                            - switch to slot N (also: sN)\n"
        "  team N,...                          - team preview order (e.g. 2,1,3,4,5,6)\n"
        "  moves                               - show available moves\n"
        "  switches                            - show switch options\n"
        "  help                                - show this help\n"
        "  feed human | feed raw               - toggle summarized/raw stream\n"
        "\nAdvanced: You can still prefix with p1:/p2: to target a side directly.\n"
        f"Current default side: {active_side}"
    )


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
                requests[current] = req
            except Exception:
                # Ignore malformed JSON; keep last good request
                pass

def main():
    debug_print("Starting CLI battle interface", "MAIN")
    parser = argparse.ArgumentParser()
    parser.add_argument("p1", help="Path to Player 1 team file (Showdown importable)")
    parser.add_argument("p2", help="Path to Player 2 team file")
    parser.add_argument("--format", default="gen7ou")
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
    parser.set_defaults(p2_ai=True, humanize=True)
    args = parser.parse_args()
    debug_print(f"Command line args parsed: {args}", "MAIN")

    debug_print("Packing team files...", "TEAMS")
    p1_team = pack_team(args.p1)
    p2_team = pack_team(args.p2)
    debug_print(f"P1 team packed length: {len(p1_team)}, P2 team packed length: {len(p2_team)}", "TEAMS")

    debug_print("Initializing Pokemon Showdown simulator...", "SIMULATOR")
    sim = ShowdownWrapper(formatid=args.format)
    sim.send(f'>player p1 {{"name":"P1","team":"{p1_team}"}}')
    sim.send(f'>player p2 {{"name":"P2","team":"{p2_team}"}}')
    debug_print("Simulator initialized and teams sent", "SIMULATOR")

    # Track current request state for each side
    requests: Dict[str, dict] = {}
    # Track last shown request id to avoid spamming
    shown_rqid: Dict[str, Optional[int]] = {"p1": None, "p2": None}
    preview_done = set()
    battle = _new_battle_state()

    print("Battle started. Type 'help' for commands.\n")
    humanize_mode = args.humanize
    debug_print("Entering main battle loop", "MAIN")

    try:
        while True:
            # show simulator output and capture requests
            out = sim.read()
            debug_print(f"Simulator read output: {len(out) if out else 0} lines", "SIMULATOR")
            if out:
                winner = _process_output(out, humanize_mode, args.side, requests, shown_rqid, battle)
                debug_print(f"Process output result - Winner: {winner}", "MAIN")
                if winner:
                    print(f"\nBattle over. Winner: {winner}")
                    return

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
                            if args.no_auto_preview:
                                debug_print(f"Manual team preview mode for {side}", "PREVIEW")
                                print(f"Team preview requested for {side}.")
                                print("Enter order as comma-separated indices (e.g., 2,1,3,4,5,6)")
                                print(f"Press Enter for default: {default_order}")
                                user = input(f"{side} team> ").strip()
                                order = user if user else default_order
                                sim.send(f">{side} team {order}")
                                preview_done.add(side)
                                print(f"[manual] Sent team preview order for {side}: {order}")
                                debug_print(f"Manual team preview sent for {side}: {order}", "PREVIEW")
                            else:
                                debug_print(f"Auto team preview for {side}: {default_order}", "PREVIEW")
                                sim.send(f">{side} team {default_order}")
                                preview_done.add(side)
                                print(f"[auto] Sent team preview order for {side}: {default_order}")
                                debug_print(f"Auto team preview sent for {side}: {default_order}", "PREVIEW")

                # further UI is handled inside _process_output

                # If P2 is AI, respond automatically to new P2 requests
                if args.p2_ai:
                    ai_req = requests.get('p2')
                    debug_print(f"P2 AI check - Has request: {bool(ai_req)}", "AI")
                    if ai_req:
                        ai_rqid = ai_req.get('rqid')
                        if ai_rqid is None:
                            ai_rqid = hash(str(ai_req.get('active')) + str(ai_req.get('forceSwitch')))
                        debug_print(f"P2 AI request ID: {ai_rqid}, last shown: {shown_rqid.get('p2')}", "AI")
                        if shown_rqid.get('p2') != ai_rqid:
                            # Prefer team preview default if needed
                            if ai_req.get('teamPreview'):
                                debug_print("P2 AI handling team preview", "AI")
                                team = (ai_req.get('side') or {}).get('pokemon') or []
                                n = len(team)
                                if n:
                                    order = ",".join(str(i) for i in range(1, n + 1))
                                    sim.send(f">p2 team {order}")
                                    print(f"[p2-ai] team {order}")
                                    debug_print(f"P2 AI sent team order: {order}", "AI")
                                    shown_rqid['p2'] = ai_rqid
                                    # Drain any immediate output
                                    out2 = sim.read()
                                    if out2:
                                        w = _process_output(out2, humanize_mode, args.side, requests, shown_rqid, battle)
                                        if w:
                                            print(f"\nBattle over. Winner: {w}")
                                            return
                            # Handle forced switch
                            elif (ai_req.get('forceSwitch') or [False])[0]:
                                debug_print("P2 AI handling forced switch", "AI")
                                side = ai_req.get('side') or {}
                                poke = side.get('pokemon') or []
                                choice = None
                                for idx, p in enumerate(poke, start=1):
                                    cond = p.get('condition', '')
                                    if 'fnt' in cond:
                                        continue
                                    # try to avoid active slot if present
                                    choice = idx
                                    break
                                if choice:
                                    sim.send(f">p2 switch {choice}")
                                    print(f"[p2-ai] switch {choice}")
                                    debug_print(f"P2 AI sent switch: {choice}", "AI")
                                    shown_rqid['p2'] = ai_rqid
                                    out2 = sim.read()
                                    if out2:
                                        w = _process_output(out2, humanize_mode, args.side, requests, shown_rqid, battle)
                                        if w:
                                            print(f"\nBattle over. Winner: {w}")
                                            return
                            # Handle moves
                            elif ai_req.get('active'):
                                debug_print("P2 AI handling moves", "AI")
                                moves = (ai_req.get('active') or [{}])[0].get('moves', [])
                                choices = [i + 1 for i, m in enumerate(moves) if not m.get('disabled')]
                                if not choices and moves:
                                    choices = [1]
                                if choices:
                                    pick = random.choice(choices)
                                    sim.send(f">p2 move {pick}")
                                    print(f"[p2-ai] move {pick}")
                                    debug_print(f"P2 AI sent move: {pick}", "AI")
                                    shown_rqid['p2'] = ai_rqid
                                    out2 = sim.read()
                                    if out2:
                                        w = _process_output(out2, humanize_mode, args.side, requests, shown_rqid, battle)
                                        if w:
                                            print(f"\nBattle over. Winner: {w}")
                                            return

            # get user input
            prompt_side = args.side.upper()
            cmd = input(f"{prompt_side}> ")
            debug_print(f"User input: '{cmd}'", "INPUT")
            if not cmd:
                continue
            if cmd.lower() in ("quit", "exit"):
                debug_print("User requested exit", "INPUT")
                break

            # prepend proper prefix
            if cmd == 'help':
                print(_help_text(args.side))
                continue

            # Introspection helpers
            if cmd.startswith('p1:') and cmd[3:].strip() in ('moves', 'switches'):
                action = cmd[3:].strip()
                req = requests.get('p1')
                if action == 'moves':
                    print(_pretty_moves(req))
                else:
                    print(_pretty_switches(req))
                continue
            if cmd.startswith('p2:') and cmd[3:].strip() in ('moves', 'switches'):
                action = cmd[3:].strip()
                req = requests.get('p2')
                if action == 'moves':
                    print(_pretty_moves(req))
                else:
                    print(_pretty_switches(req))
                continue

            # 1v1-friendly unprefixed commands for the active side
            lower = cmd.lower().strip()
            if lower in ("moves", "switches"):
                req = requests.get(args.side)
                if lower == "moves":
                    print(_pretty_moves(req))
                else:
                    print(_pretty_switches(req))
                continue
            # Allow bare numbers as 'move N'
            if lower.isdigit():
                sim.send(f">{args.side} move {lower}")
                print(f"[sent] {args.side} move {lower}")
                debug_print(f"Sent move command: {args.side} move {lower}", "COMMAND")
                out = sim.read()
                if out:
                    w = _process_output(out, humanize_mode, args.side, requests, shown_rqid, battle)
                    if w:
                        print(f"\nBattle over. Winner: {w}")
                        return
                continue
            # Accept tight forms like 'move3', 'm1', 's2'
            if lower.startswith('move') and lower[4:].strip().isdigit():
                num = ''.join(ch for ch in lower[4:] if ch.isdigit())
                sim.send(f">{args.side} move {num}")
                print(f"[sent] {args.side} move {num}")
                debug_print(f"Sent move command (tight form): {args.side} move {num}", "COMMAND")
                out = sim.read()
                if out:
                    w = _process_output(out, humanize_mode, args.side, requests, shown_rqid, battle)
                    if w:
                        print(f"\nBattle over. Winner: {w}")
                        return
                continue
            if lower.startswith('m') and lower[1:].isdigit():
                num = lower[1:]
                sim.send(f">{args.side} move {num}")
                print(f"[sent] {args.side} move {num}")
                debug_print(f"Sent move command (m shorthand): {args.side} move {num}", "COMMAND")
                out = sim.read()
                if out:
                    w = _process_output(out, humanize_mode, args.side, requests, shown_rqid, battle)
                    if w:
                        print(f"\nBattle over. Winner: {w}")
                        return
                continue
            if lower.startswith('s') and lower[1:].isdigit():
                num = lower[1:]
                sim.send(f">{args.side} switch {num}")
                print(f"[sent] {args.side} switch {num}")
                debug_print(f"Sent switch command: {args.side} switch {num}", "COMMAND")
                out = sim.read()
                if out:
                    w = _process_output(out, humanize_mode, args.side, requests, shown_rqid, battle)
                    if w:
                        print(f"\nBattle over. Winner: {w}")
                        return
                continue
            if lower.startswith("move ") or lower.startswith("switch ") or lower.startswith("team "):
                sim.send(f">{args.side} {cmd.strip()}")
                print(f"[sent] {args.side} {cmd.strip()}")
                debug_print(f"Sent full command: {args.side} {cmd.strip()}", "COMMAND")
                out = sim.read()
                if out:
                    w = _process_output(out, humanize_mode, args.side, requests, shown_rqid, battle)
                    if w:
                        print(f"\nBattle over. Winner: {w}")
                        return
                continue
            # 'team' alone -> default ordering if preview pending
            if lower == 'team':
                debug_print("Processing 'team' command", "COMMAND")
                req = requests.get(args.side) or {}
                team = (req.get('side') or {}).get('pokemon') or []
                n = len(team)
                if req.get('teamPreview') and n:
                    order = ",".join(str(i) for i in range(1, n + 1))
                    sim.send(f">{args.side} team {order}")
                    print(f"[sent] {args.side} team {order}")
                    out = sim.read()
                    if out:
                        w = _process_output(out, humanize_mode, args.side, requests, shown_rqid, battle)
                        if w:
                            print(f"\nBattle over. Winner: {w}")
                            return
                    continue

            # runtime toggle for humanized/raw feed
            if lower in ("feed human", "feed raw"):
                humanize_mode = (lower == "feed human")
                print(f"[feed] {'humanized' if humanize_mode else 'raw'}")
                continue

            if cmd.startswith("p1:"):
                sim.send(f">p1 {cmd[3:].strip()}")
                print(f"[sent] p1 {cmd[3:].strip()}")
                out = sim.read()
                if out:
                    w = _process_output(out, humanize_mode, args.side, requests, shown_rqid, battle)
                    if w:
                        print(f"\nBattle over. Winner: {w}")
                        return
            elif cmd.startswith("p2:"):
                sim.send(f">p2 {cmd[3:].strip()}")
                print(f"[sent] p2 {cmd[3:].strip()}")
                out = sim.read()
                if out:
                    w = _process_output(out, humanize_mode, args.side, requests, shown_rqid, battle)
                    if w:
                        print(f"\nBattle over. Winner: {w}")
                        return
            else:
                print("Invalid command. Try 'help' or use: move N | switch N | moves | switches | team N,...  (or prefix with p1:/p2:)")
    finally:
        sim.close()

if __name__ == "__main__":
    main()
