import asyncio
import json
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import threading

from showdown_wrapper import ShowdownWrapper, generate_random_team
import cli
from gemini_agent import init_gemini_agent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SHOWDOWN_ROOM_URL = "https://play.pokemonshowdown.com/{room}"


class BattleSession:
    """Drives a battle and streams updates to a single WebSocket client.

    Two modes:
      - remote: connect to the live Pokemon Showdown server as the user's
        account and let Gemini play *as the user* (their side). The client
        watches Gemini's reasoning here and the live battle on Showdown.
      - local: run a local simulator with the human as p1 and Gemini as p2.
    """

    def __init__(self, websocket: WebSocket, loop: asyncio.AbstractEventLoop):
        self.ws = websocket
        self.loop = loop
        self.sim = None
        self.running = False
        self.bg_thread = None
        self.remote = False
        self.ai_side = "p2"

        # State tracking
        self.requests = {}
        self.shown_rqid = {"p1": None, "p2": None}
        self.battle_state = cli._new_battle_state()
        self.current_turn = 0
        self.team_knowledge = None
        self.announced_room = False

    # ------------------------------------------------------------------ #
    # Outbound helpers (thread-safe: scheduled onto the asyncio loop)
    # ------------------------------------------------------------------ #
    def _send(self, payload: dict):
        try:
            fut = asyncio.run_coroutine_threadsafe(
                self.ws.send_text(json.dumps(payload)), self.loop
            )
            fut.result(timeout=5)
        except Exception as e:
            print(f"WS send error: {e}")

    # ------------------------------------------------------------------ #
    # Battle startup
    # ------------------------------------------------------------------ #
    async def start_battle(self, config: dict):
        self.running = True

        try:
            init_gemini_agent()
        except Exception:
            print("Warning: Gemini not configured via ENV")

        self.remote = bool(config.get("remote", True))
        battle_format = config.get("format") or "gen9randombattle"

        if self.remote:
            username = (config.get("username") or "").strip()
            password = config.get("password") or ""
            if not username:
                self._send({"type": "error", "message": "Username is required for remote battles."})
                self.running = False
                return
            try:
                from remote_showdown import RemoteShowdownWrapper

                self._send({"type": "status", "message": f"Connecting to Pokemon Showdown as {username}..."})
                self.sim = RemoteShowdownWrapper(username, password, battle_format)
            except Exception as e:
                self._send({"type": "error", "message": f"Failed to connect: {e}"})
                self.running = False
                return
            self._send({"type": "status", "message": f"Searching for a {battle_format} battle..."})
        else:
            p1_team = generate_random_team(formatid=battle_format)
            p2_team = generate_random_team(formatid=battle_format)
            self.sim = ShowdownWrapper(formatid=battle_format)
            self.sim.send(f'>player p1 {{"name":"Player","team":"{p1_team}"}}')
            self.sim.send(f'>player p2 {{"name":"Gemini Agent","team":"{p2_team}"}}')
            self.ai_side = "p2"

        self.bg_thread = threading.Thread(target=self._run_battle_loop, daemon=True)
        self.bg_thread.start()

    # ------------------------------------------------------------------ #
    # Main loop (runs in a background thread)
    # ------------------------------------------------------------------ #
    def _resolve_ai_side(self) -> str:
        """In remote mode Gemini plays as the logged-in user's side."""
        if self.remote:
            side = getattr(self.sim, "bot_side", None)
            return side or "p2"
        return "p2"

    def _maybe_announce_room(self):
        if self.remote and not self.announced_room:
            room = getattr(self.sim, "current_room", "")
            if room:
                self.announced_room = True
                self._send(
                    {
                        "type": "room",
                        "room": room,
                        "url": SHOWDOWN_ROOM_URL.format(room=room),
                    }
                )

    def _run_battle_loop(self):
        current_turn_log = ""
        while self.running:
            out = self.sim.wait_for_output(timeout=0.5)
            self._maybe_announce_room()
            ai_side = self._resolve_ai_side()

            if out:
                state_changed = False
                cli._parse_stream_lines(out, self.requests)

                for line in out:
                    current_turn_log += line + "\n"
                    if "|turn|" in line:
                        self.shown_rqid["p1"] = None
                        self.shown_rqid["p2"] = None
                        try:
                            self.current_turn = int(line.split("|turn|")[1].strip())
                            state_changed = True
                        except Exception:
                            pass

                    changed, _err = cli._update_battle_state_from_line(line, self.battle_state)
                    if changed:
                        state_changed = True

                    hum_msg = cli._humanize_line(line)
                    if hum_msg:
                        self._send({"type": "log", "message": hum_msg})

                    if "|win|" in line:
                        winner = line.split("|win|", 1)[1].strip() or "Unknown"
                        self._send({"type": "win", "winner": winner})

                # Auto-complete team preview for the AI side (remote: our side)
                for side in ("p1", "p2"):
                    req = self.requests.get(side)
                    if req and req.get("teamPreview") and self.shown_rqid.get(f"preview_{side}") is None:
                        team = (req.get("side") or {}).get("pokemon") or []
                        n = len(team)
                        if n and (not self.remote or side == ai_side):
                            order = ",".join(str(i) for i in range(1, n + 1))
                            self.sim.send(f">{side} team {order}")
                            self.shown_rqid[f"preview_{side}"] = True

                # In local mode, forward the human's (p1) request to the client.
                if not self.remote:
                    p1_req = self.requests.get("p1")
                    if p1_req or state_changed:
                        p1_rqid = None
                        if p1_req:
                            p1_rqid = p1_req.get("rqid")
                            if p1_rqid is None:
                                p1_rqid = hash(
                                    str(p1_req.get("_seq"))
                                    + "|"
                                    + str(p1_req.get("active"))
                                    + "|"
                                    + str(p1_req.get("forceSwitch"))
                                )
                        send_p1_req = None
                        if p1_req and self.shown_rqid.get("p1") != p1_rqid:
                            send_p1_req = p1_req
                            self.shown_rqid["p1"] = p1_rqid
                        self._send(
                            {
                                "type": "state_sync",
                                "battle": self.battle_state,
                                "turn": self.current_turn,
                                "p1_request": send_p1_req,
                            }
                        )
                else:
                    self._send(
                        {
                            "type": "state_sync",
                            "battle": self.battle_state,
                            "turn": self.current_turn,
                            "p1_request": None,
                        }
                    )

            # Gemini's turn (plays as ai_side; in remote that's the user's side)
            ai_req = self.requests.get(ai_side)
            if ai_req:
                ai_rqid = ai_req.get("rqid")
                if ai_rqid is None:
                    ai_rqid = hash(
                        str(ai_req.get("_seq"))
                        + "|"
                        + str(ai_req.get("active"))
                        + "|"
                        + str(ai_req.get("forceSwitch"))
                    )

                force_switch = (ai_req.get("forceSwitch") or [False])[0]
                if force_switch or self.shown_rqid.get(ai_side) != ai_rqid:
                    if ai_req.get("teamPreview"):
                        pass
                    elif ai_req.get("wait") or ai_req.get("cant"):
                        self.shown_rqid[ai_side] = ai_rqid
                    else:
                        obs = cli._create_agent_observation(
                            ai_req, self.battle_state, None, self.current_turn
                        )
                        try:
                            decision = cli._llm_agent_decision(
                                obs, self.team_knowledge, raw_log=current_turn_log
                            )
                            self._send(
                                {
                                    "type": "ai_insight",
                                    "input": decision.get("input_prompt", ""),
                                    "thoughts": decision.get("thoughts", ""),
                                    "reasoning": decision.get("reasoning", ""),
                                    "action_type": decision.get("action_type"),
                                    "choice": decision.get("choice"),
                                    "turn": self.current_turn,
                                }
                            )
                            command = cli._translate_agent_decision(decision, ai_req)
                            if command:
                                self.sim.send(f">{ai_side} {command}")
                                self.shown_rqid[ai_side] = ai_rqid
                                current_turn_log = ""
                            else:
                                switches = cli._get_available_switches(ai_req)
                                if switches:
                                    self.sim.send(f">{ai_side} switch {switches[0]['index']}")
                                    self.shown_rqid[ai_side] = ai_rqid
                        except Exception as e:
                            print(f"Error AI: {e}")
            else:
                time.sleep(0.05)

    def process_client_message(self, message: str):
        """Handle inbound messages from the client (local-mode human actions)."""
        try:
            data = json.loads(message)
            if data.get("type") == "action" and not self.remote and self.sim:
                self.sim.send(f">p1 {data['action']}")
        except Exception as e:
            print(f"Error parsing client msg: {e}")

    def stop(self):
        self.running = False
        if self.sim:
            try:
                self.sim.close()
            except Exception:
                pass
        if self.bg_thread:
            self.bg_thread.join(timeout=1.0)


@app.websocket("/ws/battle")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    loop = asyncio.get_running_loop()
    session = BattleSession(websocket, loop)
    started = False

    try:
        while True:
            message = await websocket.receive_text()
            if not started:
                # First message must be the connection config.
                try:
                    data = json.loads(message)
                except Exception:
                    data = {}
                config = data.get("config", data) if isinstance(data, dict) else {}
                await session.start_battle(config)
                started = True
            else:
                session.process_client_message(message)

    except WebSocketDisconnect:
        session.stop()
    except Exception as e:
        print(f"WS error: {e}")
        session.stop()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
