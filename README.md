# CLI-Mon Showdown

A terminal-based Pokémon battle CLI that drives the official Pokémon Showdown simulator for accurate mechanics, quick testing, and lightweight play.

Note: You need a local clone of Pokémon Showdown. This repo expects it at `pokemon-showdown/` in the project root.

## Features

- Accurate engine: uses the official Pokémon Showdown simulator
- AI opponents: Gemini AI agent for strategic battle decisions
- Teams: load Showdown import/export text files
- CLI-first: fast feedback loop and readable battle feed
- Random battles: generate teams via Showdown

## Project Structure

- `src/cli_mon_showdown/` - installable Python package (CLI, wrapper, Gemini agent)
- `cli.py` - shim so `cli-mon` still works locally
- `pokemon-showdown/` - expected checkout of the Node simulator
- `teams/` - example team files in Showdown format
- `BATTLE_FIXES.md` - notes on battle handling improvements

## Requirements

- Python 3.10+
- Node.js 18+
- A local checkout of `smogon/pokemon-showdown` (default path `pokemon-showdown/`)

## Quick Start

### Install from PyPI (once published)

```bash
pip install cli-mon-showdown
cli-mon --help
```

### Run from a local clone

```powershell
git clone https://github.com/papichoolo/cli-mon-showdown.git
cd cli-mon-showdown

python -m venv .venv
.venv\Scripts\activate

# Install the package in editable mode (includes Python dependencies)
pip install -e .

# Fetch the Showdown simulator
git clone https://github.com/smogon/pokemon-showdown.git
cd pokemon-showdown
npm ci
cd ..

# Run a battle with sample teams
cli-mon teams/p1.txt teams/p2.txt --format gen7ou
```

## Gemini AI Agent Configuration

The CLI includes an optional Gemini AI agent that can play as Player 2, making strategic decisions based on battle state analysis. This provides a more challenging and realistic opponent compared to the default random AI.

### Prerequisites

1. **Google AI API Key**: You need access to Google's Gemini API
   - Get an API key from [Google AI Studio](https://aistudio.google.com/apikey)
   - The API may require billing setup depending on usage

2. **Python Dependencies**: Install the required packages
   ```powershell
   pip install -r requirements.txt
   ```

### Configuration

Set your API key using one of these methods:

**Option 1: Environment Variable (Recommended)**
```powershell
# PowerShell (persistent)
[Environment]::SetEnvironmentVariable("GOOGLE_AI_API_KEY", "your-api-key-here", "User")

# PowerShell (current session only)
$env:GOOGLE_AI_API_KEY = "your-api-key-here"
```

**Option 2: Alternative Environment Variable**
```powershell
$env:GEMINI_API_KEY = "your-api-key-here"
```

### Usage with Gemini AI

Once configured, the Gemini AI agent will automatically be used for Player 2 when the `--p2-ai` flag is enabled (which is the default):

```powershell
# Gemini AI will control Player 2 automatically
cli-mon teams/p1.txt teams/p2.txt --format gen7ou

# Support for Random Battles as well
cli-mon --randbat
```

### Features of the Gemini AI Agent

- **Strategic Analysis**: Evaluates complex battle states including HP, status conditions, type matchups, and team composition
- **Advanced Decision Making**: Considers win conditions, hazard management, momentum, and endgame scenarios
- **Competitive Play Style**: Follows high-level competitive Pokemon principles and strategies
- **Fallback Safety**: Automatically falls back to basic heuristics if API calls fail

### Model Configuration

The default model is `gemini-2.5-flash-lite` for optimal performance and cost. Advanced users can modify the model in `gemini_agent.py`:

```python
# In gemini_agent.py, modify the init_gemini_agent function
agent = init_gemini_agent(model_name="gemini-2.5-flash")  # More capable but slower/costlier
```

Available models:
- `gemini-2.5-flash-lite` (default): Fast, cost-effective
- `gemini-2.5-flash`: More capable, higher cost
- `gemini-2.0-flash-exp`: Experimental features

### Troubleshooting Gemini Setup

- **"No API key found"**: Ensure your environment variable is set correctly and restart your terminal
- **API errors**: Check that your API key is valid and you have sufficient quota
- **Import errors**: Run `pip install -r requirements.txt` to install dependencies
- **Fallback behavior**: If Gemini fails, the system automatically uses random decisions with a warning message


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

- Python: this project uses the standard library plus optional AI dependencies. See `requirements.txt` for AI agent dependencies.
- Node: used to run the Showdown simulator and its CLI utilities (`simulate-battle`, `pack-team`, `validate-team`, `generate-team`).
- Showdown path: by default the code looks for `pokemon-showdown/pokemon-showdown`. Keep the folder at the project root or adjust the code if you move it.

## CLI Usage

Basic:

```powershell
cli-mon <p1_team> <p2_team> [--format FORMAT] [flags]
```

Random battle (no team files required):

```powershell
cli-mon --randbat --format gen7randombattle
```

### Flags

- p1: path to Player 1 team file (Showdown importable).
- p2: path to Player 2 team file.
- --format FORMAT: Showdown format id. Default: gen7ou. Examples: gen7ou, gen9ou, gen7randombattle.
- --randbat: generate random teams for both players (ignores p1/p2 positional args).
- --no-auto-preview: disable automatic team preview ordering; you’ll be prompted to choose.
- --side {p1|p2}: which side unprefixed commands control. Default: p1.
- --p2-ai / --no-p2-ai: enable/disable AI for Player 2. When enabled with Gemini configured, uses Gemini AI agent. Default: enabled.
- --humanize / --raw: show a summarized human-readable feed (default) or raw Showdown log lines.
- --window / --no-window: render a minimal in-terminal game window (default) or print plain text only.
- --debug: print additional debug information.

Examples:

```powershell
# Gen 7 OU with built teams
cli-mon teams/p1.txt teams/p2.txt --format gen7ou

# Random battle using Showdown’s generator
cli-mon --randbat --format gen7randombattle

# Control p2 manually and show raw stream
cli-mon teams/p1.txt teams/p2.txt --side p2 --no-p2-ai --raw

# Disable the windowed UI and team auto-preview
cli-mon teams/p1.txt teams/p2.txt --no-window --no-auto-preview

# Play against Gemini AI with debug information
cli-mon teams/p1.txt teams/p2.txt --format gen9ou --debug --p2-ai
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

## Packaging and Release

### Local build

```bash
python -m pip install --upgrade build twine
python -m build
```

Artifacts will land in `dist/`. Install one with `pip install dist/cli_mon_showdown-<version>-py3-none-any.whl`.

### TestPyPI dry run

```bash
python -m twine upload --repository testpypi dist/*
python -m pip install --index-url https://test.pypi.org/simple/ cli-mon-showdown
```

### Production release

1. Bump the version in `pyproject.toml`.
2. Tag the commit (`git tag v0.1.1 && git push origin v0.1.1`).
3. Upload with `python -m twine upload dist/*` or trigger the GitHub Action described below.

### GitHub Actions automation

Store a PyPI token as the `PYPI_API_TOKEN` repository secret (optionally scope it with an environment named `pypi`).
The workflow in `.github/workflows/publish.yml` publishes whenever a tag that looks like `v*` is pushed.

