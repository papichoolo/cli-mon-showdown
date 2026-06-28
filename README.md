# CLI-Mon Showdown

A Pokémon battle tool that drives the official Pokémon Showdown simulator for
accurate mechanics. It ships in three flavors:

- a terminal **CLI** battle runner (`cli.py`)
- a **web** version: a FastAPI WebSocket server (`server.py`) + a Vite frontend (`frontend/`)
- an agent **dashboard** (`dashboard.py`) for inspecting AI state

The opponent is an LLM agent driven through **OpenRouter** (LangChain).

> Note: You need a local clone of Pokémon Showdown at `pokemon-showdown/` in the project root.

## Requirements

- Python 3.10+ (developed against 3.12)
- Node.js 18+ (used to run the Showdown simulator and the Vite frontend)
- A local checkout of `smogon/pokemon-showdown`
- An **OpenRouter API key** ([openrouter.ai/keys](https://openrouter.ai/keys))

## Setup

### 1. Get the Pokémon Showdown simulator

The code expects the simulator at `pokemon-showdown/` in the project root.

```bash
git clone https://github.com/smogon/pokemon-showdown.git
cd pokemon-showdown
npm ci
cd ..
```

`npm ci` produces the compiled `dist/` and the `pokemon-showdown` CLI binary that
this project shells out to (`simulate-battle`, `pack-team`, `validate-team`,
`generate-team`).

### 2. Install Python dependencies

**Linux / macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configure your API key

The LLM agent reads `OPENROUTER_API_KEY` (and falls back to `OPENAI_API_KEY`).
Create a `.env` file in the project root:

```dotenv
OPENROUTER_API_KEY=sk-or-your-key-here
```

`.env` is git-ignored — never commit real keys. If you change the model, the
default is `openai/gpt-oss-120b` (see `gemini_agent.py`).

| Variable | Required | Purpose |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | yes | LLM opponent via OpenRouter |
| `OPENAI_API_KEY` | no | Fallback if `OPENROUTER_API_KEY` is unset |

## Running

### Quick start (one command)

`dev.py` bootstraps the environment (creates `.venv`, installs Python + frontend
deps), verifies prerequisites, then starts and supervises the **server**,
**dashboard**, and **frontend** together with colored, interleaved logs. Press
`Ctrl-C` once to shut the whole stack down cleanly (the Showdown node processes
are reaped automatically).

```bash
make dev          # or: python3 dev.py
```

This brings up:

- battle server: `http://127.0.0.1:8000` (WebSocket at `/ws/battle`)
- dashboard:     `http://127.0.0.1:8080`
- frontend:      `http://127.0.0.1:5173`

Useful flags:

```bash
python3 dev.py --no-install     # skip dependency install (faster restarts)
python3 dev.py --no-frontend    # server + dashboard only
python3 dev.py --host 0.0.0.0   # expose on the network
python3 dev.py --server-port 9000 --dashboard-port 9090 --frontend-port 3000
```

`make stop` kills any stray `uvicorn` / `vite` processes if something is left over.

> You still need the `pokemon-showdown/` clone (see Setup) and an API key in
> `.env`. `dev.py` checks for these and tells you what's missing.

The individual services can also be started by hand:

### CLI battle runner

Activate the virtualenv first (`source .venv/bin/activate` or
`.\.venv\Scripts\Activate.ps1`).

```bash
# Battle with sample teams (LLM agent controls Player 2 by default)
python cli.py teams/p1.txt teams/p2.txt --format gen7ou

# Random battle, no team files required
python cli.py --randbat --format gen7randombattle
```

### Web version (server + frontend) — manual

Terminal 1 — start the WebSocket server on port `8000` (endpoint `/ws/battle`,
a gen7 random battle with the LLM as Player 2):

```bash
python server.py
# or: uvicorn server:app --host 0.0.0.0 --port 8000
```

Terminal 2 — start the Vite dev frontend (connects to `ws://localhost:8000/ws/battle`):

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (typically `http://localhost:5173`).

### Agent dashboard — manual

Serves `dashboard.html` on port `8080`, reading `agent_state.json`:

```bash
python dashboard.py
# or: uvicorn dashboard:app --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080`.

## CLI Usage

```bash
python cli.py <p1_team> <p2_team> [--format FORMAT] [flags]
```

### Flags

- `p1` / `p2`: paths to team files (Showdown importable format).
- `--format FORMAT`: Showdown format id. Default: `gen7ou`. Examples: `gen7ou`, `gen9ou`, `gen7randombattle`.
- `--randbat`: generate random teams for both players (ignores `p1`/`p2`).
- `--no-auto-preview`: disable automatic team preview ordering.
- `--side {p1|p2}`: which side unprefixed commands control. Default: `p1`.
- `--p2-ai` / `--no-p2-ai`: enable/disable the LLM agent for Player 2. Default: enabled.
- `--humanize` / `--raw`: summarized human-readable feed (default) or raw Showdown log lines.
- `--window` / `--no-window`: minimal in-terminal game window (default) or plain text.
- `--debug`: print additional debug information.

Examples:

```bash
# Control p2 manually and show raw stream
python cli.py teams/p1.txt teams/p2.txt --side p2 --no-p2-ai --raw

# Play against the LLM with debug information
python cli.py teams/p1.txt teams/p2.txt --format gen9ou --debug --p2-ai
```

## Teams

Team files use Pokémon Showdown's import/export text format, for example:

```
Charizard @ Life Orb
Ability: Solar Power
EVs: 252 SpA / 4 SpD / 252 Spe
Timid Nature
- Solar Beam
- Fire Blast
- Air Slash
- Hidden Power Ice
```

Teams are packed and validated via Showdown's CLI (`pack-team` and `validate-team`).
If validation fails, the Showdown error output is shown.

## Project Structure

- `cli.py` – main CLI battle runner
- `dev.py` – one-command launcher that bootstraps and supervises the full stack
- `server.py` – FastAPI WebSocket server backing the web version
- `frontend/` – Vite web client (connects over WebSocket to `server.py`)
- `dashboard.py` / `dashboard.html` – agent state dashboard (reads `agent_state.json`)
- `gemini_agent.py` – LLM battle agent (LangChain + OpenRouter)
- `showdown_wrapper.py` – thin wrapper around the Showdown Node process
- `poke_env_agent.py` / `run_poke_env.py` / `remote_showdown.py` – poke-env / remote server play
- `teams/` – example team files in Showdown format
- `pokemon-showdown/` – local clone of the simulator (you provide this)

## Troubleshooting

- **"node: not found" / "file not found"**: ensure Node.js is installed and `node` is on your PATH.
- **Pokémon Showdown not found**: confirm `pokemon-showdown/` exists at the project root and `npm ci` ran inside it.
- **"No OPENROUTER_API_KEY found"**: set it in `.env` (or your shell). The agent falls back to a dummy key and calls will fail without a real one.
- **Frontend can't connect**: start `server.py` first; the frontend expects `ws://localhost:8000/ws/battle`.
- **Port already in use**: the server uses `8000`, the dashboard `8080`, and Vite `5173`. Stop conflicting processes or change the ports.
- **Validation errors**: check that your team is legal in the chosen `--format`.
- **Terminal window not rendering**: try `--no-window`.

---

Uses the official Pokémon Showdown simulator.
