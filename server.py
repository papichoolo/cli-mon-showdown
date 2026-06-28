import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import threading
import queue

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


class BattleSession:
    def __init__(self, websocket: WebSocket):
        self.ws = websocket
        self.sim = None
        self.running = False
        self.bg_thread = None

        # State tracking
        self.requests = {}
        self.shown_rqid = {"p1": None, "p2": None}
        self.battle_state = cli._new_battle_state()
        self.current_turn = 0
        self.team_knowledge = None

    async def start_battle(self):
        self.running = True

        # Initialize Gemini directly
        try:
            init_gemini_agent()
        except:
            print("Warning: Gemini not configured via ENV")

        p1_team = generate_random_team(formatid="gen7randombattle")
        p2_team = generate_random_team(formatid="gen7randombattle")

        self.sim = ShowdownWrapper(formatid="gen7randombattle")
        self.sim.send(f'>player p1 {{"name":"Player","team":"{p1_team}"}}')
        self.sim.send(f'>player p2 {{"name":"Gemini Agent","team":"{p2_team}"}}')

        # Run simulator polling in background thread so we don't block asyncio
        self.bg_thread = threading.Thread(target=self._run_battle_loop)
        self.bg_thread.start()

    def _run_battle_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self.running:
            out = self.sim.wait_for_output(timeout=0.5)
            if out:
                state_changed = False

                # Parse for agent requests? 
                cli._parse_stream_lines(out, self.requests)
                for line in out:
                    if "|turn|" in line:
                        self.shown_rqid["p1"] = None
                        self.shown_rqid["p2"] = None
                        try:
                            self.current_turn = int(line.split("|turn|")[1].strip())
                            state_changed = True
                        except:
                            pass

                    changed, err = cli._update_battle_state_from_line(
                        line, self.battle_state
                    )
                    if changed:
                        state_changed = True

                    # Also send a summarized log to the frontend
                    hum_msg = cli._humanize_line(line)
                    if hum_msg:
                        loop.run_until_complete(
                            self.ws.send_text(
                                json.dumps({"type": "log", "message": hum_msg})
                            )
                        )

                p1_req = self.requests.get("p1")
                if p1_req or state_changed:
                    # Calculate a robust request ID (fallback to hash if rqid is missing)
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

                    sync_data = {
                        "type": "state_sync",
                        "battle": self.battle_state,
                        "turn": self.current_turn,
                        "p1_request": send_p1_req,
                    }
                    if send_p1_req:
                        self.shown_rqid["p1"] = p1_rqid
                    loop.run_until_complete(self.ws.send_text(json.dumps(sync_data)))

            # Handle Gemini AI turn
            ai_req = self.requests.get("p2")
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

                if force_switch or self.shown_rqid.get("p2") != ai_rqid:
                    if ai_req.get("wait") or ai_req.get("cant"):
                        self.shown_rqid["p2"] = ai_rqid
                        continue

                    obs = cli._create_agent_observation(
                        ai_req, self.battle_state, None, self.current_turn
                    )
                    try:
                        decision = cli._llm_agent_decision(obs, self.team_knowledge)

                        # Send insight immediately to frontend
                        insight = {
                            "type": "ai_insight",
                            "thoughts": decision.get("thoughts", ""),
                            "reasoning": decision.get("reasoning", ""),
                        }
                        loop.run_until_complete(self.ws.send_text(json.dumps(insight)))

                        command = cli._translate_agent_decision(decision, ai_req)
                        if command:
                            self.sim.send(f">p2 {command}")
                            self.shown_rqid["p2"] = ai_rqid
                        else:
                            # Fallback switch
                            switches = cli._get_available_switches(ai_req)
                            if switches:
                                self.sim.send(f">p2 switch {switches[0]['index']}")
                                self.shown_rqid["p2"] = ai_rqid
                    except Exception as e:
                        print(f"Error AI: {e}")

        loop.close()

    def process_client_message(self, message):
        """Process incoming actions from the websocket (Player 1)"""
        try:
            data = json.loads(message)
            if data["type"] == "action":
                # action will be like 'move 1' or 'switch 3'
                self.sim.send(f">p1 {data['action']}")
        except Exception as e:
            print(f"Error parsing client msg: {e}")

    def stop(self):
        self.running = False
        if self.sim:
            self.sim.close()
        if self.bg_thread:
            self.bg_thread.join(timeout=1.0)


@app.websocket("/ws/battle")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session = BattleSession(websocket)
    await session.start_battle()

    try:
        while True:
            message = await websocket.receive_text()
            session.process_client_message(message)

    except WebSocketDisconnect:
        session.stop()
    except Exception as e:
        print(f"WS error: {e}")
        session.stop()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
