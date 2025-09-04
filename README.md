# CLI Pokémon Showdown

A command-line Pokémon battle simulator with competitive moveset integration, dynamic team building, and streamlined CLI experience.

## Features

- **Competitive Movesets**: Automatically applies EVs, IVs, item, nature, and ability from Smogon sets (via `movesets.json`).
- **Dynamic Pokémon Creation**: Fetches live stats, moves, and abilities from PokéAPI.
- **Turn-Based Battle System**: Handles player/opponent turns, move execution, and effects.
- **Accurate Damage Calculation**: Implements official Pokémon damage formula (STAB, type, crits, weather).
- **Status & Secondary Effects**: Supports burn, poison, paralysis, and secondary move effects.
- **Customizable Pokémon**: Users can override moveset, nature, item, etc.
- **Streamlined CLI**: No redundant prompts; moveset info shown after selection.

## Project Structure

- `cli.py` — Main CLI battle simulator (entry point)
- `test.py` — Competitive moveset selection logic
- `items.py` — Item database (Python)
- `items.ts` — Item database (TypeScript)
- `movesets.json` — Smogon competitive movesets
- `.env` — API keys and environment variables

## Setup Instructions

1. **Clone the repository**
   ```powershell
   git clone https://github.com/papichoolo/cli-mon-showdown.git
   cd cli-mon-showdown
   ```

2. **Create a virtual environment**
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies**
   *(If `requirements.txt` is missing, install manually: `prompt_toolkit`, `requests`, `python-dotenv`)*
   ```powershell
   pip install -r requirements.txt
   ```

4. **Configure API keys**
   - Edit `.env` with your PokéAPI and (optionally) Azure/Gemini keys.

## How to Run

```powershell
python cli.py
```

## Example Usage

```
🌟 Welcome to Pokemon Battle Simulator! 🌟
==================================================
Enter the name of your Pokémon: Charizard
Selected: Charizard
Enter the name of opponent Pokémon: Blastoise
Selected: Blastoise

🔥 BATTLE START! 🔥
Charizard vs Blastoise
...
```

## Notes
- Moveset details are shown in the CLI after selection.
- Supports both static and dynamic Pokémon/item databases.
- For advanced usage, see code comments in `cli.py` and `test.py`.

---
Created by papichoolo. Competitive sets courtesy of Smogon University.
