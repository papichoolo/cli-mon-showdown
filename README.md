# CLI-Mon-Showdown

A terminal-based Pokémon battle CLI that drives the official Pokémon Showdown simulator for accurate mechanics, quick testing, and lightweight play.

Note: You need a local clone of Pokémon Showdown. This repo expects it at `pokemon-showdown/` in the project root.

## Features

- Accurate engine: uses the official Pokémon Showdown simulator
- Teams: load Showdown import/export text files
- CLI-first: fast feedback loop and readable battle feed
- Random battles: generate teams via Showdown

## Project Structure

- `cli.py` – main CLI battle runner
- `showdown_wrapper.py` – thin wrapper around the Showdown Node process
- `teams/` – example team files in Showdown format
- `BATTLE_FIXES.md` – notes on battle handling improvements

## Requirements

- Python 3.8+
- Node.js 16+
- A local checkout of `smogon/pokemon-showdown`

## Quick Start

PowerShell (Windows):

```powershell
git clone https://github.com/papichoolo/cli-mon-showdown.git
cd cli-mon-showdown

# Optional: create a virtualenv (no external Python deps required)
python -m venv .venv
.venv\Scripts\activate

# Get Pokémon Showdown inside this project
git clone https://github.com/smogon/pokemon-showdown.git
cd pokemon-showdown
npm ci
cd ..

# Run a battle with sample teams
python cli.py teams/p1.txt teams/p2.txt --format gen7ou
```

Bash (macOS/Linux):

```bash
git clone https://github.com/papichoolo/cli-mon-showdown.git
cd cli-mon-showdown

python3 -m venv .venv
source .venv/bin/activate

git clone https://github.com/smogon/pokemon-showdown.git
cd pokemon-showdown && npm ci && cd ..

python3 cli.py teams/p1.txt teams/p2.txt --format gen7ou
```

## Setup Details

- Python: this project uses only the standard library; `requirements.txt` is intentionally empty.
- Node: used to run the Showdown simulator and its CLI utilities (`simulate-battle`, `pack-team`, `validate-team`, `generate-team`).
- Showdown path: by default the code looks for `pokemon-showdown/pokemon-showdown`. Keep the folder at the project root or adjust the code if you move it.

## CLI Usage

Basic:

```powershell
python cli.py <p1_team> <p2_team> [--format FORMAT] [flags]
```

Random battle (no team files required):

```powershell
python cli.py --randbat --format gen7randombattle
```

### Flags

- p1: path to Player 1 team file (Showdown importable).
- p2: path to Player 2 team file.
- --format FORMAT: Showdown format id. Default: gen7ou. Examples: gen7ou, gen9ou, gen7randombattle.
- --randbat: generate random teams for both players (ignores p1/p2 positional args).
- --no-auto-preview: disable automatic team preview ordering; you’ll be prompted to choose.
- --side {p1|p2}: which side unprefixed commands control. Default: p1.
- --p2-ai / --no-p2-ai: enable/disable simple random-choice AI for Player 2. Default: enabled.
- --humanize / --raw: show a summarized human-readable feed (default) or raw Showdown log lines.
- --window / --no-window: render a minimal in-terminal game window (default) or print plain text only.
- --debug: print additional debug information.

Examples:

```powershell
# Gen 7 OU with built teams
python cli.py teams/p1.txt teams/p2.txt --format gen7ou

# Random battle using Showdown’s generator
python cli.py --randbat --format gen7randombattle

# Control p2 manually and show raw stream
python cli.py teams/p1.txt teams/p2.txt --side p2 --no-p2-ai --raw

# Disable the windowed UI and team auto-preview
python cli.py teams/p1.txt teams/p2.txt --no-window --no-auto-preview
```

## Teams

Team files should be in Pokémon Showdown’s import/export text format, for example:

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

When you run the CLI, your teams are packed and validated via Showdown’s CLI (`pack-team` and `validate-team`). If validation fails, the error output from Showdown is shown.

## Troubleshooting

- “node: not found” or “file not found”: ensure Node.js is installed and `node` is on your PATH.
- Pokémon Showdown not found: confirm the folder exists at `pokemon-showdown/` and run `npm ci` inside it.
- Validation errors: check that your team is legal in the chosen `--format`.
- Terminal window not rendering: some terminals may not support the UI; try `--no-window`.

---

Created by papichoolo. Uses the official Pokémon Showdown simulator.

