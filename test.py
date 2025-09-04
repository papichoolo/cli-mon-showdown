
import json
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter

def load_movesets():
    with open("movesets.json", "r", encoding="utf-8") as f:
        return json.load(f)

def pick_from_list(options, message="Pick one:"):
    for i, opt in enumerate(options):
        print(f"{i+1}. {opt}")
    while True:
        choice = prompt(f"{message} (1-{len(options)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            selected = options[int(choice)-1]
            # If option is a dict, print moveset details
            if isinstance(selected, dict):
                print("\nMoveset details:")
                if 'moves' in selected:
                    print("Moves:", ', '.join(selected['moves']) if isinstance(selected['moves'], list) else selected['moves'])
                if 'item' in selected:
                    print("Item:", selected['item'])
                if 'nature' in selected:
                    print("Nature:", selected['nature'])
                if 'ability' in selected:
                    print("Ability:", selected['ability'])
                if 'evs' in selected:
                    print("EVs:", selected['evs'])
                if 'ivs' in selected:
                    print("IVs:", selected['ivs'])
            return selected
        print("Invalid choice.")

def flatten_moves(moves):
    # Flattens moves with slashes (lists) by picking the first option
    flat = []
    for m in moves:
        if isinstance(m, list):
            flat.append(m[0])
        else:
            flat.append(m)
    return flat

def return_moveset(pokemon_name):
    movesets = load_movesets()
    name = pokemon_name.strip().replace("-", " ").title().replace(" ", "-") if pokemon_name not in movesets else pokemon_name
    if name not in movesets:
        print(f"No 1v1/OU movesets found for {pokemon_name}. We currently only support 1v1 and OU formats for battle.")
        return None
    formats = list(movesets[name].keys())
    # Always auto-select 1v1 if available, else ou, else first available
    if "1v1" in formats:
        format_choice = "1v1"
    elif "ou" in formats:
        format_choice = "ou"
    else:
        format_choice = formats[0]
    sets = movesets[name][format_choice]
    set_names = list(sets.keys())

    # User picks which set to use
    set_choice = pick_from_list(set_names, "Pick a moveset")
    chosen = sets[set_choice]
    # Pick first option for moves, item, nature if list
    moves = flatten_moves(chosen["moves"])
    item = chosen["item"][0] if isinstance(chosen.get("item"), list) else chosen.get("item")
    nature = chosen["nature"][0] if isinstance(chosen.get("nature"), list) else chosen.get("nature")
    ability = chosen.get("ability")
    evs = chosen.get("evs", {})
    ivs = chosen.get("ivs", {})
    return {
        "moves": moves,
        "item": item,
        "nature": nature,
        "ability": ability,
        "evs": evs,
        "ivs": ivs,
        "format": format_choice,
        "set_name": set_choice
    }


# def main():
#     movesets = load_movesets()
#     poke_names = sorted(movesets.keys())
#     poke_completer = WordCompleter(poke_names, ignore_case=True)
#     pokemon = prompt("Enter Pokémon name: ", completer=poke_completer).strip()
#     result = return_moveset(pokemon)
#     if result:
#         print(f"\nCompetitive moveset for {pokemon}:")
#         print(f"Format: {result['format']}")
#         print(f"Set: {result['set_name']}")
#         print(f"Moves: {', '.join(result['moves'])}")
#         print(f"Item: {result['item']}")
#         print(f"Nature: {result['nature']}")
#         print(f"Ability: {result['ability']}")
#         print(f"EVs: {result['evs']}")
#         print(f"IVs: {result['ivs']}")
#     else:
#         print(f"No competitive moveset found for {pokemon}.")

# if __name__ == "__main__":
#     main()