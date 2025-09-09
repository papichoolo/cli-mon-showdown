# CLI Pokémon Showdown

A command-line Pokémon battle simulator that integrates with Pokémon Showdown's simulator engine for accurate battle mechanics, team building, and competitive play.

**Note:Pokemon Showndown is required for the CLI to work so dont forget to clone https://github.com/smogon/pokemon-showdown.git**
 
## Features

- **Pokémon Showdown Integration**: Uses the official Pokémon Showdown simulator for accurate battle mechanics
- **Team Building**: Import and export teams in Showdown format
- **Command-Line Interface**: Clean, streamlined CLI experience for battles
- **Team Utilities**: JavaScript utilities for team parsing and validation using @pkmn libraries
- **Automated Battles**: Support for automated battle scenarios and testing

## Project Structure


- `cli.py` — CLI battle simulator
- `showdown_wrapper.py` — Python wrapper for Pokémon Showdown simulator
- `teamutils.js` — Team parsing and utilities using @pkmn libraries
- `teams/` — Sample team files in Showdown format
- `BATTLE_FIXES.md` — Documentation of battle system improvements


## CLI Flags

| Flag | Description |
| ---- | ----------- |
| `p1` | Path to Player 1’s team file in Showdown export format (required). |
| `p2` | Path to Player 2’s team file (required). |
| `--format FORMAT` | Pokémon Showdown battle format ID (default: `gen7ou`). |
| `--no-auto-preview` | Disable automatic team preview ordering; prompt for manual order. |
| `--side {p1,p2}` | Side controlled via unprefixed commands in the CLI (default: `p1`). |
| `--p2-ai` / `--no-p2-ai` | Enable (default) or disable random move selection for Player 2. |
| `--humanize` / `--raw` | Show human‑friendly event summaries (default) or raw Showdown log lines. |
| `--window` / `--no-window` | Render the in-terminal game window (default) or show plain text output. |


## Prerequisites

- **Python 3.7+**
- **Node.js 14+**
- **Pokémon Showdown** (cloned separately)

## Setup Instructions

1. **Clone the repository**
   ```powershell
   git clone https://github.com/papichoolo/cli-mon-showdown.git
   cd cli-mon-showdown
   ```

2. **Install Python dependencies**
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Install Node.js dependencies**
   ```powershell
   npm install
   ```

4. **Clone Pokémon Showdown**
   ```powershell
   git clone https://github.com/smogon/pokemon-showdown.git
   cd pokemon-showdown
   npm install
   cd ..
   ```

## How to Run

### Basic Battle Simulation
```powershell
python cli.py teams/p1.txt teams/p2.txt
```

### Team Utilities
```powershell
node teamutils.js teams/p1.txt
```

## Team Format

Teams should be in Pokémon Showdown's importable format. Example:

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

## Dependencies

### Python
- Core Python libraries for CLI and battle logic

### Node.js
- `@pkmn/dex` - Pokémon data and utilities
- `@pkmn/sets` - Team parsing and validation
- `@pkmn/sim` - Simulator integration

## Important Notes

- **Pokémon Showdown folder is NOT included** in this repository. Clone it separately as shown in setup instructions.
- Team files in `teams/` directory are examples - create your own or use Showdown's team builder.
- The simulator requires the Pokémon Showdown engine to be properly installed and accessible.

---

Created by papichoolo. Uses Pokémon Showdown's simulator engine and @pkmn libraries.
