# CLI Pokémon Showdown

This project is a command-line based Pokémon battle simulator that uses the PokéAPI to fetch Pokémon data, including stats, moves, and abilities. It allows users to select their Pokémon and an opponent, and then engage in a turn-based battle.

## Features

- **Dynamic Pokémon Creation**: Fetches and creates Pokémon using live data from the PokéAPI.
- **Turn-Based Battle System**: A complete battle loop that handles player and opponent turns, move execution, and end-of-turn effects.
- **Accurate Damage Calculation**: Implements the official Pokémon damage formula, including STAB, type effectiveness, critical hits, and weather modifiers.
- **Status Conditions and Secondary Effects**: Supports various status conditions (e.g., burn, poison, paralysis) and secondary move effects.
- **Customizable Pokémon**: Allows users to customize their Pokémon's moveset, nature, and item.

## Setup

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/papichoolo/cli-mon-showdown.git
    cd cli-mon-showdown
    ```

2.  **Create a virtual environment**:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
    ```

3.  **Install the dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: A `requirements.txt` file may need to be created if one does not already exist.)*

## How to Run

To start the battle simulator, run the following command in your terminal:

```bash
python cli.py
```

You will be prompted to enter the names of your Pokémon and your opponent's Pokémon. The battle will then begin, and you can select moves for your Pokémon during each turn.

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
