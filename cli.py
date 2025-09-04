
import random
import time
import sys
import json
import requests
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from copy import deepcopy
from test import return_moveset
# Autocomplete support
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter

# Enums for better type safety
API = "https://pokeapi.co/api/v2"
class StatusCondition(Enum):
    NONE = "none"
    BURN = "burn"
    FREEZE = "freeze"
    PARALYSIS = "paralysis"
    POISON = "poison"
    BADLY_POISON = "badly_poison"
    SLEEP = "sleep"

class Weather(Enum):
    CLEAR = "clear"
    RAIN = "rain"
    HARSH_SUNLIGHT = "harsh_sunlight"
    SANDSTORM = "sandstorm"
    HAIL = "hail"
    SNOW = "snow"

class VolatileStatus(Enum):
    CONFUSED = "confused"
    FLINCH = "flinch"
    TRAPPED = "trapped"
    CURSED = "cursed"
    LEECH_SEED = "leech_seed"
    ATTRACT = "attract"
    TAUNT = "taunt"

# Type effectiveness chart
TYPE_EFFECTIVENESS = {
    'Normal': {'Rock': 0.5, 'Ghost': 0, 'Steel': 0.5},
    'Fire': {'Fire': 0.5, 'Water': 0.5, 'Grass': 2, 'Ice': 2, 'Bug': 2, 'Rock': 0.5, 'Dragon': 0.5, 'Steel': 2},
    'Water': {'Fire': 2, 'Water': 0.5, 'Grass': 0.5, 'Ground': 2, 'Rock': 2, 'Dragon': 0.5},
    'Electric': {'Water': 2, 'Electric': 0.5, 'Grass': 0.5, 'Ground': 0, 'Flying': 2, 'Dragon': 0.5},
    'Grass': {'Fire': 0.5, 'Water': 2, 'Grass': 0.5, 'Poison': 0.5, 'Ground': 2, 'Flying': 0.5, 'Bug': 0.5, 'Rock': 2, 'Dragon': 0.5, 'Steel': 0.5},
    'Ice': {'Fire': 0.5, 'Water': 0.5, 'Grass': 2, 'Ice': 0.5, 'Ground': 2, 'Flying': 2, 'Dragon': 2, 'Steel': 0.5},
    'Fighting': {'Normal': 2, 'Ice': 2, 'Poison': 0.5, 'Flying': 0.5, 'Psychic': 0.5, 'Bug': 0.5, 'Rock': 2, 'Ghost': 0, 'Dark': 2, 'Steel': 2, 'Fairy': 0.5},
    'Poison': {'Grass': 2, 'Poison': 0.5, 'Ground': 0.5, 'Rock': 0.5, 'Ghost': 0.5, 'Steel': 0, 'Fairy': 2},
    'Ground': {'Fire': 2, 'Electric': 2, 'Grass': 0.5, 'Poison': 2, 'Flying': 0, 'Bug': 0.5, 'Rock': 2, 'Steel': 2},
    'Flying': {'Electric': 0.5, 'Grass': 2, 'Ice': 0.5, 'Fighting': 2, 'Bug': 2, 'Rock': 0.5, 'Steel': 0.5},
    'Psychic': {'Fighting': 2, 'Poison': 2, 'Psychic': 0.5, 'Dark': 0, 'Steel': 0.5},
    'Bug': {'Fire': 0.5, 'Grass': 2, 'Fighting': 0.5, 'Poison': 0.5, 'Flying': 0.5, 'Psychic': 2, 'Ghost': 0.5, 'Dark': 2, 'Steel': 0.5, 'Fairy': 0.5},
    'Rock': {'Fire': 2, 'Ice': 2, 'Fighting': 0.5, 'Ground': 0.5, 'Flying': 2, 'Bug': 2, 'Steel': 0.5},
    'Ghost': {'Normal': 0, 'Psychic': 2, 'Ghost': 2, 'Dark': 0.5},
    'Dragon': {'Dragon': 2, 'Steel': 0.5, 'Fairy': 0},
    'Dark': {'Fighting': 0.5, 'Psychic': 2, 'Bug': 0.5, 'Ghost': 2, 'Dark': 0.5, 'Fairy': 0.5},
    'Steel': {'Fire': 0.5, 'Water': 0.5, 'Electric': 0.5, 'Ice': 2, 'Rock': 2, 'Steel': 0.5, 'Fairy': 2},
    'Fairy': {'Fire': 0.5, 'Fighting': 2, 'Poison': 0.5, 'Dragon': 2, 'Dark': 2, 'Steel': 0.5}
}

# Pokemon Natures
NATURES = {
    'Hardy': {'increased': None, 'decreased': None},
    'Lonely': {'increased': 'attack', 'decreased': 'defense'},
    'Brave': {'increased': 'attack', 'decreased': 'speed'},
    'Adamant': {'increased': 'attack', 'decreased': 'sp_attack'},
    'Naughty': {'increased': 'attack', 'decreased': 'sp_defense'},
    'Bold': {'increased': 'defense', 'decreased': 'attack'},
    'Docile': {'increased': None, 'decreased': None},
    'Relaxed': {'increased': 'defense', 'decreased': 'speed'},
    'Impish': {'increased': 'defense', 'decreased': 'sp_attack'},
    'Lax': {'increased': 'defense', 'decreased': 'sp_defense'},
    'Timid': {'increased': 'speed', 'decreased': 'attack'},
    'Hasty': {'increased': 'speed', 'decreased': 'defense'},
    'Serious': {'increased': None, 'decreased': None},
    'Jolly': {'increased': 'speed', 'decreased': 'sp_attack'},
    'Naive': {'increased': 'speed', 'decreased': 'sp_defense'},
    'Modest': {'increased': 'sp_attack', 'decreased': 'attack'},
    'Mild': {'increased': 'sp_attack', 'decreased': 'defense'},
    'Quiet': {'increased': 'sp_attack', 'decreased': 'speed'},
    'Bashful': {'increased': None, 'decreased': None},
    'Rash': {'increased': 'sp_attack', 'decreased': 'sp_defense'},
    'Calm': {'increased': 'sp_defense', 'decreased': 'attack'},
    'Gentle': {'increased': 'sp_defense', 'decreased': 'defense'},
    'Sassy': {'increased': 'sp_defense', 'decreased': 'speed'},
    'Careful': {'increased': 'sp_defense', 'decreased': 'sp_attack'},
    'Quirky': {'increased': None, 'decreased': None},
}

@dataclass
class SecondaryEffect:
    """Represents a secondary effect of a move"""
    chance: int  # Percentage chance
    effect_type: str  # 'status', 'stat_change', 'flinch', etc.
    target: str  # 'self', 'opponent', 'both'
    value: Any  # The effect value (status condition, stat changes, etc.)

@dataclass
class Move:
    name: str
    type: str
    category: str  # 'Physical', 'Special', 'Status'
    power: int
    accuracy: int
    pp: int
    max_pp: int
    secondary_effects: List[SecondaryEffect] = field(default_factory=list)
    priority: int = 0  # Move priority (-6 to +5)
    contact: bool = False  # Whether the move makes contact
    description: str = ""
    
    def __post_init__(self):
        self.max_pp = self.pp

@dataclass
class Ability:
    name: str
    description: str
    effect_type: str  # 'passive', 'on_switch', 'on_attack', etc.

@dataclass
class Item:
    name: str
    description: str
    effect_type: str  # 'stat_boost', 'status_immunity', 'berry', etc.
    value: Any = None

@dataclass
class StatChanges:
    """Tracks stat stage changes (-6 to +6)"""
    attack: int = 0
    defense: int = 0
    sp_attack: int = 0
    sp_defense: int = 0
    speed: int = 0
    accuracy: int = 0
    evasion: int = 0
    
    def get_multiplier(self, stat: str) -> float:
        """Get the multiplier for a stat based on its stage"""
        stage = getattr(self, stat, 0)
        if stage >= 0:
            return (2 + stage) / 2
        else:
            return 2 / (2 - stage)

@dataclass
class Pokemon:
    name: str
    types: List[str]
    level: int
    hp: int
    max_hp: int
    attack: int
    defense: int
    sp_attack: int
    sp_defense: int
    speed: int
    moves: List[Move]
    ability: Optional[Ability] = None
    item: Optional[Item] = None
    nature: str = "Hardy"
    status: StatusCondition = StatusCondition.NONE
    volatile_status: List[VolatileStatus] = field(default_factory=list)
    stat_changes: StatChanges = field(default_factory=StatChanges)
    sleep_turns: int = 0
    confusion_turns: int = 0
    
    def __post_init__(self):
        self.max_hp = self.hp
        self.apply_nature()
    
    def apply_nature(self):
        """Apply nature stat modifications"""
        nature_data = NATURES.get(self.nature, NATURES['Hardy'])
        increased = nature_data['increased']
        decreased = nature_data['decreased']
        
        if increased:
            original_stat = getattr(self, increased)
            setattr(self, increased, int(original_stat * 1.1))
        
        if decreased:
            original_stat = getattr(self, decreased)
            setattr(self, decreased, int(original_stat * 0.9))
    
    def get_effective_stat(self, stat: str) -> int:
        """Get stat with all modifiers applied"""
        base_stat = getattr(self, stat)
        multiplier = self.stat_changes.get_multiplier(stat)
        
        # Apply status conditions
        if stat == 'attack' and self.status == StatusCondition.BURN:
            multiplier *= 0.5
        elif stat == 'speed' and self.status == StatusCondition.PARALYSIS:
            multiplier *= 0.5
        
        return int(base_stat * multiplier)

@dataclass
class BattleField:
    """Represents the battlefield state"""
    weather: Weather = Weather.CLEAR
    weather_turns: int = 0
    hazards: Dict[str, List[str]] = field(default_factory=dict)  # 'player'/'opponent' -> list of hazards
    terrain: Optional[str] = None
    terrain_turns: int = 0

def fetch_pokemon_data(name: str) -> dict:
    resp = requests.get(f"{API}/pokemon/{name.lower()}")
    resp.raise_for_status()
    return resp.json()
def fetch_pokemon_base_stats(name: str) -> dict:
    resp = requests.get(f"{API}/pokemon/{name.lower()}")
    resp.raise_for_status()
    data = resp.json()
    return {stat['stat']['name']: stat['base_stat'] for stat in data['stats']}

def fetch_nature_data(nature: str) -> dict:
    resp = requests.get(f"{API}/nature/{nature.lower()}")
    resp.raise_for_status()
    return resp.json()

def get_random_nature() -> str:
    resp = requests.get(f"{API}/nature")
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return random.choice(results)["name"]

def fetch_move_data(name: str) -> dict:
    resp = requests.get(f"{API}/move/{name.lower().replace(' ', '-').replace("'", '')}")
    resp.raise_for_status()
    return resp.json()


# Enhanced Pokemon Database
POKEMON_DATABASE = {
    'Charizard': {
        'types': ['Fire', 'Flying'],
        'base_stats': {'hp': 78, 'attack': 84, 'defense': 78, 'sp_attack': 109, 'sp_defense': 85, 'speed': 100},
        'abilities': [
            Ability('Blaze', 'Powers up Fire-type moves when HP is low', 'conditional'),
            Ability('Solar Power', 'Boosts Sp. Atk in harsh sunlight but loses HP', 'weather')
        ],
        'level_up_moves': [
            Move('Scratch', 'Normal', 'Physical', 40, 100, 35, 35, [], 0, True),
            Move('Ember', 'Fire', 'Special', 40, 100, 25, 25, 
                 [SecondaryEffect(10, 'status', 'opponent', StatusCondition.BURN)]),
            Move('Flamethrower', 'Fire', 'Special', 90, 100, 15, 15,
                 [SecondaryEffect(10, 'status', 'opponent', StatusCondition.BURN)]),
            Move('Fire Blast', 'Fire', 'Special', 110, 85, 5, 5,
                 [SecondaryEffect(10, 'status', 'opponent', StatusCondition.BURN)]),
            Move('Air Slash', 'Flying', 'Special', 75, 95, 15, 15,
                 [SecondaryEffect(30, 'flinch', 'opponent', True)]),
            Move('Dragon Pulse', 'Dragon', 'Special', 85, 100, 10, 10),
            Move('Solar Beam', 'Grass', 'Special', 120, 100, 10, 10),
            Move('Thunder Punch', 'Electric', 'Physical', 75, 100, 15, 15,
                 [SecondaryEffect(10, 'status', 'opponent', StatusCondition.PARALYSIS)], 0, True),
            Move('Roost', 'Flying', 'Status', 0, 100, 5, 5),
            Move('Sunny Day', 'Fire', 'Status', 0, 100, 5, 5),
        ]
    },
    'Blastoise': {
        'types': ['Water'],
        'base_stats': {'hp': 79, 'attack': 83, 'defense': 100, 'sp_attack': 85, 'sp_defense': 105, 'speed': 78},
        'abilities': [
            Ability('Torrent', 'Powers up Water-type moves when HP is low', 'conditional'),
            Ability('Rain Dish', 'Restores HP in rain', 'weather')
        ],
        'level_up_moves': [
            Move('Tackle', 'Normal', 'Physical', 40, 100, 35, 35, [], 0, True),
            Move('Water Gun', 'Water', 'Special', 40, 100, 25, 25),
            Move('Hydro Pump', 'Water', 'Special', 110, 80, 5, 5),
            Move('Surf', 'Water', 'Special', 90, 100, 15, 15),
            Move('Ice Beam', 'Ice', 'Special', 90, 100, 10, 10,
                 [SecondaryEffect(10, 'status', 'opponent', StatusCondition.FREEZE)]),
            Move('Blizzard', 'Ice', 'Special', 110, 70, 5, 5,
                 [SecondaryEffect(10, 'status', 'opponent', StatusCondition.FREEZE)]),
            Move('Earthquake', 'Ground', 'Physical', 100, 100, 10, 10),
            Move('Flash Cannon', 'Steel', 'Special', 80, 100, 10, 10,
                 [SecondaryEffect(10, 'stat_change', 'opponent', {'sp_defense': -1})]),
            Move('Rain Dance', 'Water', 'Status', 0, 100, 5, 5),
            Move('Withdraw', 'Water', 'Status', 0, 100, 40, 40),
        ]
    },
    'Venusaur': {
        'types': ['Grass', 'Poison'],
        'base_stats': {'hp': 80, 'attack': 82, 'defense': 83, 'sp_attack': 100, 'sp_defense': 100, 'speed': 80},
        'abilities': [
            Ability('Overgrow', 'Powers up Grass-type moves when HP is low', 'conditional'),
            Ability('Chlorophyll', 'Boosts Speed in harsh sunlight', 'weather')
        ],
        'level_up_moves': [
            Move('Tackle', 'Normal', 'Physical', 40, 100, 35, 35, [], 0, True),
            Move('Vine Whip', 'Grass', 'Physical', 45, 100, 25, 25, [], 0, True),
            Move('Giga Drain', 'Grass', 'Special', 75, 100, 10, 10),
            Move('Solar Beam', 'Grass', 'Special', 120, 100, 10, 10),
            Move('Sludge Bomb', 'Poison', 'Special', 90, 100, 10, 10,
                 [SecondaryEffect(30, 'status', 'opponent', StatusCondition.POISON)]),
            Move('Earth Power', 'Ground', 'Special', 90, 100, 10, 10,
                 [SecondaryEffect(10, 'stat_change', 'opponent', {'sp_defense': -1})]),
            Move('Sleep Powder', 'Grass', 'Status', 0, 75, 15, 15),
            Move('Toxic', 'Poison', 'Status', 0, 90, 10, 10),
            Move('Leech Seed', 'Grass', 'Status', 0, 90, 10, 10),
            Move('Synthesis', 'Grass', 'Status', 0, 100, 5, 5),
        ]
    },
    'Pikachu': {
        'types': ['Electric'],
        'base_stats': {'hp': 35, 'attack': 55, 'defense': 40, 'sp_attack': 50, 'sp_defense': 50, 'speed': 90},
        'abilities': [
            Ability('Static', 'May cause paralysis when contacted', 'contact'),
            Ability('Lightning Rod', 'Draws Electric moves and boosts Sp. Atk', 'redirect')
        ],
        'level_up_moves': [
            Move('Quick Attack', 'Normal', 'Physical', 40, 100, 30, 30, [], 1, True),
            Move('Thunder Shock', 'Electric', 'Special', 40, 100, 30, 30,
                 [SecondaryEffect(10, 'status', 'opponent', StatusCondition.PARALYSIS)]),
            Move('Thunderbolt', 'Electric', 'Special', 90, 100, 15, 15,
                 [SecondaryEffect(10, 'status', 'opponent', StatusCondition.PARALYSIS)]),
            Move('Thunder', 'Electric', 'Special', 110, 70, 10, 10,
                 [SecondaryEffect(30, 'status', 'opponent', StatusCondition.PARALYSIS)]),
            Move('Iron Tail', 'Steel', 'Physical', 100, 75, 15, 15,
                 [SecondaryEffect(30, 'stat_change', 'opponent', {'defense': -1})], 0, True),
            Move('Grass Knot', 'Grass', 'Special', 60, 100, 20, 20),
            Move('Double Team', 'Normal', 'Status', 0, 100, 15, 15),
            Move('Agility', 'Normal', 'Status', 0, 100, 30, 30),
            Move('Thunder Wave', 'Electric', 'Status', 0, 90, 20, 20),
            Move('Light Screen', 'Psychic', 'Status', 0, 100, 30, 30),
        ]
    },
    'Garchomp': {
        'types': ['Dragon', 'Ground'],
        'base_stats': {'hp': 108, 'attack': 130, 'defense': 95, 'sp_attack': 80, 'sp_defense': 85, 'speed': 102},
        'abilities': [
            Ability('Sand Veil', 'Boosts evasion in a sandstorm', 'weather'),
            Ability('Rough Skin', 'Inflicts damage on contact', 'contact')
        ],
        'level_up_moves': [
            Move('Tackle', 'Normal', 'Physical', 40, 100, 35, 35, [], 0, True),
            Move('Sand Attack', 'Ground', 'Status', 0, 100, 15, 15),
            Move('Dragon Claw', 'Dragon', 'Physical', 80, 100, 15, 15, [], 0, True),
            Move('Earthquake', 'Ground', 'Physical', 100, 100, 10, 10),
            Move('Stone Edge', 'Rock', 'Physical', 100, 80, 5, 5),
            Move('Outrage', 'Dragon', 'Physical', 120, 100, 10, 10),
            Move('Fire Blast', 'Fire', 'Special', 110, 85, 5, 5,
                 [SecondaryEffect(10, 'status', 'opponent', StatusCondition.BURN)]),
            Move('Sandstorm', 'Rock', 'Status', 0, 100, 10, 10),
            Move('Swords Dance', 'Normal', 'Status', 0, 100, 20, 20),
            Move('Stealth Rock', 'Rock', 'Status', 0, 100, 20, 20),
        ]
    },
    'Alakazam': {
        'types': ['Psychic'],
        'base_stats': {'hp': 55, 'attack': 50, 'defense': 45, 'sp_attack': 135, 'sp_defense': 95, 'speed': 120},
        'abilities': [
            Ability('Synchronize', 'Passes on status conditions', 'status'),
            Ability('Inner Focus', 'Prevents flinching', 'flinch_immunity')
        ],
        'level_up_moves': [
            Move('Teleport', 'Psychic', 'Status', 0, 100, 20, 20, [], -6),
            Move('Confusion', 'Psychic', 'Special', 50, 100, 25, 25,
                 [SecondaryEffect(10, 'volatile_status', 'opponent', VolatileStatus.CONFUSED)]),
            Move('Psychic', 'Psychic', 'Special', 90, 100, 10, 10,
                 [SecondaryEffect(10, 'stat_change', 'opponent', {'sp_defense': -1})]),
            Move('Psyshock', 'Psychic', 'Special', 80, 100, 10, 10),
            Move('Focus Blast', 'Fighting', 'Special', 120, 70, 5, 5,
                 [SecondaryEffect(10, 'stat_change', 'opponent', {'sp_defense': -1})]),
            Move('Shadow Ball', 'Ghost', 'Special', 80, 100, 15, 15,
                 [SecondaryEffect(20, 'stat_change', 'opponent', {'sp_defense': -1})]),
            Move('Dazzling Gleam', 'Fairy', 'Special', 80, 100, 10, 10),
            Move('Calm Mind', 'Psychic', 'Status', 0, 100, 20, 20),
            Move('Recover', 'Normal', 'Status', 0, 100, 5, 5),
            Move('Reflect', 'Psychic', 'Status', 0, 100, 20, 20),
        ]
    }
}

# Items database
ITEMS = {
    'Leftovers': Item('Leftovers', 'Restores HP every turn', 'healing', 1/16),
    'Choice Band': Item('Choice Band', 'Boosts Attack but locks into one move', 'stat_boost', {'attack': 1.5}),
    'Choice Specs': Item('Choice Specs', 'Boosts Sp. Atk but locks into one move', 'stat_boost', {'sp_attack': 1.5}),
    'Choice Scarf': Item('Choice Scarf', 'Boosts Speed but locks into one move', 'stat_boost', {'speed': 1.5}),
    'Focus Sash': Item('Focus Sash', 'Survives a KO hit with 1 HP when at full HP', 'survival', None),
    'Life Orb': Item('Life Orb', 'Boosts attack power but causes recoil', 'power_boost', 1.3),
    'Flame Orb': Item('Flame Orb', 'Burns the holder after one turn', 'status_orb', StatusCondition.BURN),
    'Toxic Orb': Item('Toxic Orb', 'Badly poisons the holder after one turn', 'status_orb', StatusCondition.BADLY_POISON),
    'Sitrus Berry': Item('Sitrus Berry', 'Restores HP when below 50%', 'berry', 0.25),
    'Lum Berry': Item('Lum Berry', 'Cures any status condition', 'status_cure', None),
}

class BattleSimulator:
    def __init__(self):
        self.player_pokemon = None
        self.opponent_pokemon = None
        self.battlefield = BattleField()
        self.turn_count = 0
        
    def calculate_stats_at_level(self, base_stats: Dict[str, int], level: int = 100) -> Dict[str, int]:
        """Calculate stats at a given level using the standard formula"""
        calculated = {}
        for stat, base in base_stats.items():
            if stat == 'hp':
                calculated[stat] = int(((2 * base + 31) * level) / 100) + level + 10
            else:
                calculated[stat] = int(((2 * base + 31) * level) / 100) + 5
        return calculated
    
    def create_pokemon(self, name: str, moveset, level: int = 100, nature: Optional[str] = None,
                   ability_index: int = 0, item_name: Optional[str] = None) -> Pokemon:
        """Create a Pokemon instance using live data from PokéAPI"""
        import math
        selected_moves = moveset
        data = fetch_pokemon_data(name)
        stats_raw = {s["stat"]["name"]: s["base_stat"] for s in data["stats"]}
        #selected_moves = return_moveset(data["name"].lower())
        #print(f"Selected moves for {name}: {selected_moves}")
        types = [t["type"]["name"] for t in data["types"]]
        moves_available = [m["move"]["name"] for m in data["moves"]]
        #selected_moves = random.sample(moves_available, k=min(4, len(moves_available)))
        nature = nature or get_random_nature()
        nat_data = fetch_nature_data(nature)
        inc = nat_data["increased_stat"]["name"] if nat_data["increased_stat"] else None
        dec = nat_data["decreased_stat"]["name"] if nat_data["decreased_stat"] else None

        def apply_nature(stat: str, base: int) -> int:
            if stat == inc:
                return math.floor(base * 1.1)
            elif stat == dec:
                return math.floor(base * 0.9)
            return base

        base_hp = ((2 * stats_raw["hp"] * level) // 100) + level + 10
        stats = {
            "hp": base_hp,
            "attack": apply_nature("attack", ((2 * stats_raw["attack"] * level) // 100) + 5),
            "defense": apply_nature("defense", ((2 * stats_raw["defense"] * level) // 100) + 5),
            "sp_attack": apply_nature("sp_attack", ((2 * stats_raw["special-attack"] * level) // 100) + 5),
            "sp_defense": apply_nature("sp_defense", ((2 * stats_raw["special-defense"] * level) // 100) + 5),
            "speed": apply_nature("speed", ((2 * stats_raw["speed"] * level) // 100) + 5)
        }

        item = ITEMS.get(item_name) if item_name else None

        move_objs = []
        #print(f"Fetching move data for: {selected_moves}")
        for move_name in selected_moves['moves']:
            try:
                move_data = fetch_move_data(move_name)
                #print(move_data)
                move_objs.append(Move(
                    name=move_data["name"].title().replace("-", " "),
                    type=move_data["type"]["name"],
                    category=move_data["damage_class"]["name"].title(),
                    power=move_data["power"] or 0,
                    accuracy=move_data["accuracy"] or 100,
                    pp=move_data["pp"] or 10,
                    max_pp=move_data["pp"] or 10,
                    secondary_effects=[],
                    priority=move_data["priority"] or 0,
                    contact=False,  # Simplified
                    description=next((e["short_effect"] for e in move_data["effect_entries"] if e["language"]["name"] == "en"), "")
                ))
            except Exception as e:
                print(f"Could not fetch move {move_name}: {e}")
                continue

        return Pokemon(
            name=name.title(),
            types=types,
            level=level,
            hp=stats["hp"],
            max_hp=stats["hp"],
            attack=stats["attack"],
            defense=stats["defense"],
            sp_attack=stats["sp_attack"],
            sp_defense=stats["sp_defense"],
            speed=stats["speed"],
            moves=move_objs,
            #ability=Ability(name="Unknown"),
            item=item,
            nature=nature.title()
        )
    
    def print_animated_health_bar(self, pokemon: Pokemon, width: int = 25):
        """Print an animated health bar with status indicators"""
        hp_percentage = pokemon.hp / pokemon.max_hp
        filled_width = int(hp_percentage * width)
        empty_width = width - filled_width
        
        # Color coding based on HP percentage
        if hp_percentage > 0.5:
            color = '\033[92m'  # Green
        elif hp_percentage > 0.2:
            color = '\033[93m'  # Yellow
        else:
            color = '\033[91m'  # Red
        
        bar = color + '█' * filled_width + '\033[0m' + '░' * empty_width
        
        # Status indicators
        status_text = ""
        if pokemon.status != StatusCondition.NONE:
            status_colors = {
                StatusCondition.BURN: '\033[91m',
                StatusCondition.FREEZE: '\033[96m',
                StatusCondition.PARALYSIS: '\033[93m',
                StatusCondition.POISON: '\033[95m',
                StatusCondition.BADLY_POISON: '\033[95m',
                StatusCondition.SLEEP: '\033[94m',
            }
            status_text = f" {status_colors[pokemon.status]}{pokemon.status.value.upper()}\033[0m"
        
        # Item indicator
        item_text = f" @{pokemon.item.name}" if pokemon.item else ""
        
        print(f"{pokemon.name}{item_text}: [{bar}] {pokemon.hp}/{pokemon.max_hp} HP{status_text}")
    
    def apply_weather_effects(self, pokemon: Pokemon):
        """Apply weather effects at end of turn"""
        if self.battlefield.weather == Weather.SANDSTORM:
            if not any(t in ['Rock', 'Ground', 'Steel'] for t in pokemon.types):
                damage = pokemon.max_hp // 16
                pokemon.hp = max(0, pokemon.hp - damage)
                print(f"{pokemon.name} is buffeted by the sandstorm! (-{damage} HP)")
        
        elif self.battlefield.weather == Weather.HAIL:
            if 'Ice' not in pokemon.types:
                damage = pokemon.max_hp // 16
                pokemon.hp = max(0, pokemon.hp - damage)
                print(f"{pokemon.name} is buffeted by the hail! (-{damage} HP)")
        
        elif self.battlefield.weather == Weather.RAIN:
            if pokemon.ability.name == 'Rain Dish':
                heal = pokemon.max_hp // 16
                pokemon.hp = min(pokemon.max_hp, pokemon.hp + heal)
                print(f"{pokemon.name} restored HP with Rain Dish! (+{heal} HP)")
    
    def apply_status_effects(self, pokemon: Pokemon):
        """Apply status condition effects"""
        if pokemon.status == StatusCondition.BURN:
            damage = pokemon.max_hp // 16
            pokemon.hp = max(0, pokemon.hp - damage)
            print(f"{pokemon.name} is hurt by its burn! (-{damage} HP)")
        
        elif pokemon.status == StatusCondition.POISON:
            damage = pokemon.max_hp // 8
            pokemon.hp = max(0, pokemon.hp - damage)
            print(f"{pokemon.name} is hurt by poison! (-{damage} HP)")
        
        elif pokemon.status == StatusCondition.BADLY_POISON:
            damage = pokemon.max_hp // 16 * pokemon.sleep_turns  # Use sleep_turns as poison counter
            pokemon.hp = max(0, pokemon.hp - damage)
            print(f"{pokemon.name} is hurt by bad poison! (-{damage} HP)")
            pokemon.sleep_turns += 1
    
    def apply_item_effects(self, pokemon: Pokemon):
        """Apply item effects"""
        if not pokemon.item:
            return
        
        if pokemon.item.name == 'Leftovers':
            heal = int(pokemon.max_hp * pokemon.item.value)
            if pokemon.hp < pokemon.max_hp:
                pokemon.hp = min(pokemon.max_hp, pokemon.hp + heal)
                print(f"{pokemon.name} restored HP with Leftovers! (+{heal} HP)")
        
        elif pokemon.item.name == 'Sitrus Berry' and pokemon.hp <= pokemon.max_hp // 2:
            heal = int(pokemon.max_hp * pokemon.item.value)
            pokemon.hp = min(pokemon.max_hp, pokemon.hp + heal)
            print(f"{pokemon.name} restored HP with Sitrus Berry! (+{heal} HP)")
            pokemon.item = None  # Berry is consumed
        
        elif pokemon.item.name == 'Lum Berry' and pokemon.status != StatusCondition.NONE:
            pokemon.status = StatusCondition.NONE
            print(f"{pokemon.name} cured its status with Lum Berry!")
            pokemon.item = None  # Berry is consumed
    
    def calculate_damage(self, attacker: Pokemon, defender: Pokemon, move: Move) -> Tuple[int, bool, float]:
        """Calculate damage using the official Pokemon damage formula with all modifiers"""
        if move.category == 'Status':
            return 0, False, 1.0
        
        # Check if move hits
        accuracy = move.accuracy
        if attacker.stat_changes.accuracy != 0:
            accuracy *= attacker.stat_changes.get_multiplier('accuracy')
        if defender.stat_changes.evasion != 0:
            accuracy /= defender.stat_changes.get_multiplier('evasion')
        
        if random.randint(1, 100) > accuracy:
            return -1, False, 0  # Miss
        
        # Determine attack and defense stats
        if move.category == 'Physical':
            attack_stat = attacker.get_effective_stat('attack')
            defense_stat = defender.get_effective_stat('defense')
        else:  # Special
            attack_stat = attacker.get_effective_stat('sp_attack')
            defense_stat = defender.get_effective_stat('sp_defense')
        
        # Apply item modifiers
        if attacker.item:
            if attacker.item.name == 'Choice Band' and move.category == 'Physical':
                attack_stat = int(attack_stat * attacker.item.value['attack'])
            elif attacker.item.name == 'Choice Specs' and move.category == 'Special':
                attack_stat = int(attack_stat * attacker.item.value['sp_attack'])
            elif attacker.item.name == 'Life Orb':
                attack_stat = int(attack_stat * attacker.item.value)
        
        # Base damage calculation
        level_factor = (2 * attacker.level + 10) / 250
        attack_ratio = attack_stat / defense_stat
        base_damage = (level_factor * attack_ratio * move.power + 2)
        
        # Apply modifiers
        modifier = 1.0
        
        # Random factor (85-100%)
        modifier *= random.uniform(0.85, 1.0)
        
        # STAB (Same Type Attack Bonus)
        if move.type in attacker.types:
            modifier *= 1.5
        
        # Type effectiveness
        type_effectiveness = 1.0
        for defender_type in defender.types:
            capitalized_move_type = move.type.capitalize()
            capitalized_defender_type = defender_type.capitalize()
            if capitalized_move_type in TYPE_EFFECTIVENESS:
                effectiveness = TYPE_EFFECTIVENESS[capitalized_move_type].get(capitalized_defender_type, 1.0)
                type_effectiveness *= effectiveness
        modifier *= type_effectiveness
        
        # Weather modifiers
        if self.battlefield.weather == Weather.RAIN:
            if move.type == 'Water':
                modifier *= 1.5
            elif move.type == 'Fire':
                modifier *= 0.5
        elif self.battlefield.weather == Weather.HARSH_SUNLIGHT:
            if move.type == 'Fire':
                modifier *= 1.5
            elif move.type == 'Water':
                modifier *= 0.5
        
        # Critical hit (6.25% chance)
        is_critical = random.randint(1, 16) == 1
        if is_critical:
            modifier *= 1.5
        
        
        final_damage = int(base_damage * modifier)
        
        # Ensure at least 1 damage if not immune
        if final_damage < 1 and modifier > 0:
            final_damage = 1
        
        return final_damage, is_critical, modifier
    
    def apply_secondary_effects(self, attacker: Pokemon, defender: Pokemon, move: Move):
        """Apply secondary effects of moves"""
        for effect in move.secondary_effects:
            if random.randint(1, 100) <= effect.chance:
                target = attacker if effect.target == 'self' else defender
                
                if effect.effect_type == 'status':
                    if target.status == StatusCondition.NONE:
                        target.status = effect.value
                        print(f"{target.name} is {effect.value.value}!")
                
                elif effect.effect_type == 'stat_change':
                    for stat, change in effect.value.items():
                        current = getattr(target.stat_changes, stat)
                        new_value = max(-6, min(6, current + change))
                        setattr(target.stat_changes, stat, new_value)
                        
                        if change > 0:
                            print(f"{target.name}'s {stat} rose!")
                        else:
                            print(f"{target.name}'s {stat} fell!")
                
                elif effect.effect_type == 'flinch':
                    if VolatileStatus.FLINCH not in target.volatile_status:
                        target.volatile_status.append(VolatileStatus.FLINCH)
                        print(f"{target.name} flinched!")
                
                elif effect.effect_type == 'volatile_status':
                    if effect.value not in target.volatile_status:
                        target.volatile_status.append(effect.value)
                        if effect.value == VolatileStatus.CONFUSED:
                            target.confusion_turns = random.randint(1, 4)
                            print(f"{target.name} became confused!")
    
    def execute_status_move(self, user: Pokemon, target: Pokemon, move: Move):
        """Execute status moves"""
        print(f"{user.name} uses {move.name}!")
        
        # Weather moves
        if move.name == 'Sunny Day':
            self.battlefield.weather = Weather.HARSH_SUNLIGHT
            self.battlefield.weather_turns = 5
            print("The sunlight turned harsh!")
        
        elif move.name == 'Rain Dance':
            self.battlefield.weather = Weather.RAIN
            self.battlefield.weather_turns = 5
            print("It started to rain!")
        
        elif move.name == 'Sandstorm':
            self.battlefield.weather = Weather.SANDSTORM
            self.battlefield.weather_turns = 5
            print("A sandstorm kicked up!")
        
        # Healing moves
        elif move.name in ['Roost', 'Recover', 'Synthesis']:
            heal_amount = user.max_hp // 2
            if move.name == 'Synthesis':
                if self.battlefield.weather == Weather.HARSH_SUNLIGHT:
                    heal_amount = int(user.max_hp * 0.67)
                elif self.battlefield.weather in [Weather.RAIN, Weather.SANDSTORM, Weather.HAIL]:
                    heal_amount = user.max_hp // 4
            
            user.hp = min(user.max_hp, user.hp + heal_amount)
            print(f"{user.name} restored {heal_amount} HP!")
        
        # Stat-changing moves
        elif move.name == 'Swords Dance':
            user.stat_changes.attack = min(6, user.stat_changes.attack + 2)
            print(f"{user.name}'s Attack rose sharply!")
        
        elif move.name == 'Calm Mind':
            user.stat_changes.sp_attack = min(6, user.stat_changes.sp_attack + 1)
            user.stat_changes.sp_defense = min(6, user.stat_changes.sp_defense + 1)
            print(f"{user.name}'s Sp. Attack and Sp. Defense rose!")
        
        elif move.name == 'Agility':
            user.stat_changes.speed = min(6, user.stat_changes.speed + 2)
            print(f"{user.name}'s Speed rose sharply!")
        
        elif move.name == 'Double Team':
            user.stat_changes.evasion = min(6, user.stat_changes.evasion + 1)
            print(f"{user.name}'s evasiveness rose!")
        
        elif move.name == 'Withdraw':
            user.stat_changes.defense = min(6, user.stat_changes.defense + 1)
            print(f"{user.name}'s Defense rose!")
        
        # Status-inflicting moves
        elif move.name == 'Sleep Powder':
            if target.status == StatusCondition.NONE:
                target.status = StatusCondition.SLEEP
                target.sleep_turns = random.randint(1, 3)
                print(f"{target.name} fell asleep!")
            else:
                print(f"{target.name} is already affected by a status condition!")
        
        elif move.name == 'Thunder Wave':
            if target.status == StatusCondition.NONE and 'Electric' not in target.types:
                target.status = StatusCondition.PARALYSIS
                print(f"{target.name} is paralyzed!")
            else:
                print("The move had no effect!")
        
        elif move.name == 'Toxic':
            if target.status == StatusCondition.NONE:
                target.status = StatusCondition.BADLY_POISON
                target.sleep_turns = 1  # Use as poison counter
                print(f"{target.name} is badly poisoned!")
            else:
                print(f"{target.name} is already affected by a status condition!")
        
        elif move.name == 'Leech Seed':
            if VolatileStatus.LEECH_SEED not in target.volatile_status and 'Grass' not in target.types:
                target.volatile_status.append(VolatileStatus.LEECH_SEED)
                print(f"{target.name} was seeded!")
            else:
                print("The move had no effect!")
        
        # Hazard moves
        elif move.name == 'Stealth Rock':
            opponent_side = 'opponent' if user == self.player_pokemon else 'player'
            if opponent_side not in self.battlefield.hazards:
                self.battlefield.hazards[opponent_side] = []
            if 'Stealth Rock' not in self.battlefield.hazards[opponent_side]:
                self.battlefield.hazards[opponent_side].append('Stealth Rock')
                print("Pointed stones float in the air around the opposing team!")
        
        # Screen moves
        elif move.name == 'Light Screen':
            print(f"{user.name} set up Light Screen!")
        
        elif move.name == 'Reflect':
            print(f"{user.name} set up Reflect!")
    
    def check_status_prevention(self, pokemon: Pokemon) -> bool:
        """Check if Pokemon can act despite status conditions"""
        if pokemon.status == StatusCondition.SLEEP:
            if pokemon.sleep_turns > 0:
                pokemon.sleep_turns -= 1
                print(f"{pokemon.name} is fast asleep!")
                return False
            else:
                pokemon.status = StatusCondition.NONE
                print(f"{pokemon.name} woke up!")
        
        elif pokemon.status == StatusCondition.FREEZE:
            if random.randint(1, 5) == 1:
                pokemon.status = StatusCondition.NONE
                print(f"{pokemon.name} thawed out!")
            else:
                print(f"{pokemon.name} is frozen solid!")
                return False
        
        elif pokemon.status == StatusCondition.PARALYSIS:
            if random.randint(1, 4) == 1:
                print(f"{pokemon.name} is paralyzed! It can't move!")
                return False
        
        # Check confusion
        if VolatileStatus.CONFUSED in pokemon.volatile_status:
            if pokemon.confusion_turns > 0:
                pokemon.confusion_turns -= 1
                print(f"{pokemon.name} is confused!")
                if random.randint(1, 2) == 1:
                    damage = pokemon.get_effective_stat('attack') // 10
                    pokemon.hp = max(0, pokemon.hp - damage)
                    print(f"{pokemon.name} hurt itself in confusion! (-{damage} HP)")
                    return False
            else:
                pokemon.volatile_status.remove(VolatileStatus.CONFUSED)
                print(f"{pokemon.name} snapped out of confusion!")
        
        return True
    
    def get_type_effectiveness_text(self, effectiveness: float) -> str:
        """Get text description of type effectiveness"""
        if effectiveness > 1:
            return "It's super effective!"
        elif effectiveness < 1 and effectiveness > 0:
            return "It's not very effective..."
        elif effectiveness == 0:
            return "It has no effect!"
        else:
            return ""
    
    def display_battle_state(self):
        """Display the current battle state"""
        print("\n" + "="*60)
        print(f"TURN {self.turn_count} - BATTLE STATUS")
        print("="*60)
        
        # Display weather
        if self.battlefield.weather != Weather.CLEAR:
            weather_text = {
                Weather.RAIN: "Rain is falling!",
                Weather.HARSH_SUNLIGHT: "The sunlight is harsh!",
                Weather.SANDSTORM: "A sandstorm is raging!",
                Weather.HAIL: "Hail is falling!",
                Weather.SNOW: "Snow is falling!"
            }
            print(f"Weather: {weather_text[self.battlefield.weather]} ({self.battlefield.weather_turns} turns left)")
        
        # Display hazards
        for side, hazards in self.battlefield.hazards.items():
            if hazards:
                print(f"{side.title()} hazards: {', '.join(hazards)}")
        
        print()
        self.print_animated_health_bar(self.player_pokemon)
        print(f"Nature: {self.player_pokemon.nature}")
        
        print()
        self.print_animated_health_bar(self.opponent_pokemon)
        print(f"Nature: {self.opponent_pokemon.nature}")
        print("="*60)
    
    def player_turn(self):
        """Handle player's turn with autocomplete and struggle support"""
        print(f"\n{self.player_pokemon.name}'s turn!")
        # Check status conditions
        if not self.check_status_prevention(self.player_pokemon):
            return None
        # Check if all moves are out of PP (Struggle)
        if all(move.pp == 0 for move in self.player_pokemon.moves):
            print("All moves are out of PP! {self.player_pokemon.name} used Struggle!")
            return Move('Struggle', 'Normal', 'Physical', 50, 100, 1, 1, [], 0, True, description="A desperate attack that also hurts the user.")
        print("Choose a move:")
        move_names = [f"{move.name} ({move.pp}/{move.max_pp} PP)" for move in self.player_pokemon.moves]
        move_completer = WordCompleter([move.name for move in self.player_pokemon.moves], ignore_case=True)
        for i, move in enumerate(self.player_pokemon.moves):
            pp_text = f"{move.pp}/{move.max_pp} PP"
            priority_text = f" (Priority: {move.priority})" if move.priority != 0 else ""
            print(f"{i+1}. {move.name} ({move.type}, {move.category}, {move.power} power, {pp_text}){priority_text}")
        while True:
            try:
                choice = prompt("Enter move name or number (1-4): ", completer=move_completer).strip()
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(self.player_pokemon.moves):
                        selected_move = self.player_pokemon.moves[idx]
                    else:
                        print("Invalid choice! Please choose 1-4.")
                        continue
                else:
                    idx = next((i for i, m in enumerate(self.player_pokemon.moves) if m.name.lower() == choice.lower()), None)
                    if idx is not None:
                        selected_move = self.player_pokemon.moves[idx]
                    else:
                        print("Invalid move name!")
                        continue
                if selected_move.pp > 0:
                    selected_move.pp -= 1
                    return selected_move
                else:
                    print("That move is out of PP!")
            except Exception:
                print("Please enter a valid move name or number!")
    
    def opponent_turn(self):
        """Handle opponent's turn (AI)"""
        print(f"\n{self.opponent_pokemon.name}'s turn!")
        
        # Check status conditions
        if not self.check_status_prevention(self.opponent_pokemon):
            return None
        
        # Simple AI: choose a random move with PP, prefer damaging moves
        available_moves = [move for move in self.opponent_pokemon.moves if move.pp > 0]
        if not available_moves:
            print(f"{self.opponent_pokemon.name} has no moves left!")
            return None
        
        # AI strategy: prefer damaging moves when opponent is healthy
        damaging_moves = [move for move in available_moves if move.category in ['Physical', 'Special']]
        if damaging_moves and self.player_pokemon.hp > self.player_pokemon.max_hp // 2:
            selected_move = random.choice(damaging_moves)
        else:
            selected_move = random.choice(available_moves)
        
        selected_move.pp -= 1
        print(f"{self.opponent_pokemon.name} uses {selected_move.name}!")
        return selected_move
    
    def execute_move(self, attacker: Pokemon, defender: Pokemon, move: Move):
        """Execute a move and display results, with Struggle and move lock support"""
        # Move lock (Choice items)
        if hasattr(attacker, 'locked_move') and attacker.locked_move:
            if move.name != attacker.locked_move:
                print(f"{attacker.name} is locked into {attacker.locked_move}!")
                move = next((m for m in attacker.moves if m.name == attacker.locked_move), move)
        # Struggle
        if move.name == 'Struggle':
            print(f"{attacker.name} used Struggle!")
            damage = max(1, attacker.max_hp // 4)
            defender.hp = max(0, defender.hp - damage)
            print(f"{defender.name} takes {damage} damage!")
            recoil = max(1, attacker.max_hp // 4)
            attacker.hp = max(0, attacker.hp - recoil)
            print(f"{attacker.name} is hurt by recoil! (-{recoil} HP)")
            time.sleep(0.5)
            self.print_animated_health_bar(defender)
            return
        if move.category == 'Status':
            self.execute_status_move(attacker, defender, move)
            return
        result = self.calculate_damage(attacker, defender, move)
        if result[0] == -1:
            print(f"{attacker.name}'s attack missed!")
            return
        damage, is_critical, modifier = result
        if is_critical:
            print("Critical hit!")
        # Type effectiveness message
        type_effectiveness = 1.0
        for defender_type in defender.types:
            capitalized_move_type = move.type.capitalize()
            capitalized_defender_type = defender_type.capitalize()
            if capitalized_move_type in TYPE_EFFECTIVENESS:
                effectiveness = TYPE_EFFECTIVENESS[capitalized_move_type].get(capitalized_defender_type, 1.0)
                type_effectiveness *= effectiveness
        effectiveness_text = self.get_type_effectiveness_text(type_effectiveness)
        if effectiveness_text:
            print(effectiveness_text)
        # Focus Sash check
        if defender.item and defender.item.name == 'Focus Sash' and defender.hp == defender.max_hp and damage >= defender.hp:
            damage = defender.hp - 1
            print(f"{defender.name} held on with Focus Sash!")
            defender.item = None
        # Apply damage
        defender.hp = max(0, defender.hp - damage)
        print(f"{defender.name} takes {damage} damage!")
        # Apply secondary effects
        if defender.hp > 0:
            self.apply_secondary_effects(attacker, defender, move)
        # Apply contact abilities
        if move.contact and defender.ability and defender.ability.name == 'Static' and random.randint(1, 3) == 1:
            if attacker.status == StatusCondition.NONE:
                attacker.status = StatusCondition.PARALYSIS
                print(f"{attacker.name} was paralyzed by Static!")
        elif move.contact and defender.ability and defender.ability.name == 'Rough Skin':
            damage = attacker.max_hp // 8
            attacker.hp = max(0, attacker.hp - damage)
            print(f"{attacker.name} was hurt by Rough Skin! (-{damage} HP)")
        # Life Orb recoil
        if attacker.item and attacker.item.name == 'Life Orb' and move.category != 'Status':
            recoil = attacker.max_hp // 10
            attacker.hp = max(0, attacker.hp - recoil)
            print(f"{attacker.name} lost HP due to Life Orb! (-{recoil} HP)")
        # Move lock (Choice items)
        if attacker.item and attacker.item.name in ['Choice Band', 'Choice Specs', 'Choice Scarf']:
            if not hasattr(attacker, 'locked_move') or not attacker.locked_move:
                attacker.locked_move = move.name
        # Animate health bar change
        time.sleep(0.5)
        self.print_animated_health_bar(defender)
    
    def end_turn_effects(self):
        """Apply end-of-turn effects"""
        # Weather countdown
        if self.battlefield.weather_turns > 0:
            self.battlefield.weather_turns -= 1
            if self.battlefield.weather_turns == 0:
                self.battlefield.weather = Weather.CLEAR
                print("The weather cleared up!")
        
        # Apply effects to both Pokemon
        for pokemon in [self.player_pokemon, self.opponent_pokemon]:
            if pokemon.hp > 0:
                self.apply_weather_effects(pokemon)
                self.apply_status_effects(pokemon)
                self.apply_item_effects(pokemon)
                
                # Leech Seed
                if VolatileStatus.LEECH_SEED in pokemon.volatile_status:
                    drain = pokemon.max_hp // 8
                    pokemon.hp = max(0, pokemon.hp - drain)
                    opponent = self.opponent_pokemon if pokemon == self.player_pokemon else self.player_pokemon
                    opponent.hp = min(opponent.max_hp, opponent.hp + drain)
                    print(f"{pokemon.name}'s HP is sapped by Leech Seed! (-{drain} HP)")
        
        # Clear volatile status
        for pokemon in [self.player_pokemon, self.opponent_pokemon]:
            if VolatileStatus.FLINCH in pokemon.volatile_status:
                pokemon.volatile_status.remove(VolatileStatus.FLINCH)
    
    def battle_loop(self):
        """Main battle loop"""
        print(f"\n🔥 BATTLE START! 🔥")
        print(f"{self.player_pokemon.name} vs {self.opponent_pokemon.name}")
        
        while self.player_pokemon.hp > 0 and self.opponent_pokemon.hp > 0:
            self.turn_count += 1
            self.display_battle_state()
            
            # Get moves
            player_move = self.player_turn()
            opponent_move = self.opponent_turn()
            
            # Determine turn order (priority, then speed)
            player_priority = player_move.priority if player_move else -10
            opponent_priority = opponent_move.priority if opponent_move else -10
            
            player_speed = self.player_pokemon.get_effective_stat('speed')
            opponent_speed = self.opponent_pokemon.get_effective_stat('speed')
            
            # Choice Scarf speed boost
            if self.player_pokemon.item and self.player_pokemon.item.name == 'Choice Scarf':
                player_speed = int(player_speed * 1.5)
            if self.opponent_pokemon.item and self.opponent_pokemon.item.name == 'Choice Scarf':
                opponent_speed = int(opponent_speed * 1.5)
            
            # Determine who goes first
            if player_priority > opponent_priority:
                first, second = (self.player_pokemon, player_move), (self.opponent_pokemon, opponent_move)
            elif opponent_priority > player_priority:
                first, second = (self.opponent_pokemon, opponent_move), (self.player_pokemon, player_move)
            elif player_speed > opponent_speed:
                first, second = (self.player_pokemon, player_move), (self.opponent_pokemon, opponent_move)
            elif opponent_speed > player_speed:
                first, second = (self.opponent_pokemon, opponent_move), (self.player_pokemon, player_move)
            else:
                # Speed tie - random
                if random.randint(1, 2) == 1:
                    first, second = (self.player_pokemon, player_move), (self.opponent_pokemon, opponent_move)
                else:
                    first, second = (self.opponent_pokemon, opponent_move), (self.player_pokemon, player_move)
            
            # Execute moves
            attacker, move = first
            defender = self.opponent_pokemon if attacker == self.player_pokemon else self.player_pokemon
            
            if move and attacker.hp > 0:
                self.execute_move(attacker, defender, move)
            
            if defender.hp <= 0:
                break
            
            attacker, move = second
            defender = self.opponent_pokemon if attacker == self.player_pokemon else self.player_pokemon
            
            if move and attacker.hp > 0:
                self.execute_move(attacker, defender, move)
            
            if defender.hp <= 0:
                break
            
            # End of turn effects
            self.end_turn_effects()
            
            time.sleep(1)
        
        # Battle end
        print("\n" + "="*60)
        if self.player_pokemon.hp <= 0:
            print(f"💀 {self.player_pokemon.name} fainted! You lose!")
        else:
            print(f"🎉 {self.opponent_pokemon.name} fainted! You win!")
        print("="*60)
    
    def customize_pokemon(self, pokemon: Pokemon) -> Pokemon:
        """Allow player to customize Pokemon moveset, nature, item, and ability"""
        print(f"\n⚙️ Customizing {pokemon.name} ⚙️")
        
        # Choose nature
        print("\nSelect Nature:")
        nature_list = list(NATURES.keys())
        for i, nature in enumerate(nature_list[:10]):  # Show first 10 natures
            effect = NATURES[nature]
            if effect['increased'] and effect['decreased']:
                print(f"{i+1}. {nature} (+{effect['increased']}, -{effect['decreased']})")
            else:
                print(f"{i+1}. {nature} (Neutral)")
        
        print("11. More natures...")
        print("0. Keep current")
        
        choice = input("Enter choice (0-11): ")
        if choice.isdigit() and 1 <= int(choice) <= 10:
            pokemon.nature = nature_list[int(choice) - 1]
            pokemon.apply_nature()
            print(f"Nature set to {pokemon.nature}")
        
        # Choose ability
        abilities = POKEMON_DATABASE[pokemon.name]['abilities']
        if len(abilities) > 1:
            print(f"\nSelect Ability:")
            for i, ability in enumerate(abilities):
                print(f"{i+1}. {ability.name} - {ability.description}")
            
            choice = input(f"Enter choice (1-{len(abilities)}): ")
            if choice.isdigit() and 1 <= int(choice) <= len(abilities):
                pokemon.ability = abilities[int(choice) - 1]
                print(f"Ability set to {pokemon.ability.name}")
        
        # Choose item
        print(f"\nSelect Item:")
        item_list = list(ITEMS.keys())
        for i, item_name in enumerate(item_list[:10]):  # Show first 10 items
            item = ITEMS[item_name]
            print(f"{i+1}. {item.name} - {item.description}")
        
        print("11. More items...")
        print("0. No item")
        
        choice = input("Enter choice (0-11): ")
        if choice.isdigit() and 1 <= int(choice) <= 10:
            pokemon.item = ITEMS[item_list[int(choice) - 1]]
            print(f"Item set to {pokemon.item.name}")
        elif choice == "0":
            pokemon.item = None
            print("No item equipped")
        
        # Customize moveset
        print(f"\nCurrent moveset:")
        for i, move in enumerate(pokemon.moves):
            print(f"{i+1}. {move.name} ({move.type}, {move.category}, {move.power} power)")
        
        if input("\nCustomize moveset? (y/n): ").lower() == 'y':
            available_moves = POKEMON_DATABASE[pokemon.name]['level_up_moves']
            print(f"\nAvailable moves for {pokemon.name}:")
            for i, move in enumerate(available_moves):
                print(f"{i+1}. {move.name} ({move.type}, {move.category}, {move.power} power)")
            
            print("\nSelect 4 moves (enter numbers separated by spaces):")
            choice = input("Example: 1 3 5 7: ")
            try:
                indices = [int(x) - 1 for x in choice.split()]
                if len(indices) == 4 and all(0 <= i < len(available_moves) for i in indices):
                    pokemon.moves = [deepcopy(available_moves[i]) for i in indices]
                    print("Moveset updated!")
                else:
                    print("Invalid selection. Keeping current moveset.")
            except:
                print("Invalid input. Keeping current moveset.")
        
        return pokemon
    
    def select_pokemon(self, is_player: bool = True) -> Pokemon:
        """Let user search for and select a Pokémon by name (using PokéAPI) with autocomplete and apply competitive moveset/EVs/IVs/item/nature/ability"""
        player_type = "your" if is_player else "opponent"
        # For autocomplete, fetch a list of Pokémon names from PokéAPI (first 1000 for speed)
        try:
            resp = requests.get(f"{API}/pokemon?limit=1500")
            resp.raise_for_status()
            poke_names = [p['name'] for p in resp.json().get('results', [])]
        except Exception:
            poke_names = []
        poke_completer = WordCompleter(poke_names, ignore_case=True)
        while True:
            name = prompt(f"\nEnter the name of {player_type} Pokémon: ", completer=poke_completer).strip().lower()
            try:
                # Use return_moveset to get the best competitive set
                moveset = return_moveset(name)
                if not moveset:
                    print("No competitive moveset found for this Pokémon. Using default PokéAPI data.")
                    pokemon = self.create_pokemon(name, {})
                    print(f"Selected: {pokemon.name}")
                    return pokemon
                # Apply moveset fields
                print(f"\n[DEBUG] Applying competitive moveset for {name.title()}:")
                #print(json.dumps(moveset, indent=2))
                # Moves
                moves = moveset.get("moves", [])
                # Nature
                nature = moveset.get("nature", "Hardy")
                # Ability
                ability = moveset.get("ability")
                # Item
                item = moveset.get("item")
                # EVs/IVs
                evs = moveset.get("evs", {})
                ivs = moveset.get("ivs", {})
                # Create Pokémon with these fields
                pokemon = self.create_pokemon(name, moveset=moveset, nature=nature, item_name=item)
                # Set ability if present
                if ability:
                    # Try to match ability from POKEMON_DATABASE if possible
                    db_abilities = POKEMON_DATABASE.get(pokemon.name, {}).get("abilities", [])
                    for ab in db_abilities:
                        if ab.name.lower() == ability.lower():
                            pokemon.ability = ab
                            break
                    else:
                        pokemon.ability = Ability(ability, "Competitive set ability", "")
                # Set moves (overwrite with competitive set)
                if moves:
                    move_objs = []
                    for move_name in moves:
                        # Only process if move_name is a string and not a dict key
                        if not isinstance(move_name, str):
                            continue
                        # Defensive: skip if move_name is a known non-move field
                        if move_name.lower() in ["moves", "item", "nature", "ability", "evs", "ivs", "format", "set_name"]:
                            continue
                        try:
                            move_data = fetch_move_data(move_name)
                            move_objs.append(Move(
                                name=move_data["name"].title().replace("-", " "),
                                type=move_data["type"]["name"],
                                category=move_data["damage_class"]["name"].title(),
                                power=move_data["power"] or 0,
                                accuracy=move_data["accuracy"] or 100,
                                pp=move_data["pp"] or 10,
                                max_pp=move_data["pp"] or 10,
                                secondary_effects=[],
                                priority=move_data["priority"] or 0,
                                contact=False,
                                description=next((e["short_effect"] for e in move_data["effect_entries"] if e["language"]["name"] == "en"), "")
                            ))
                        except Exception as e:
                            print(f"[DEBUG] Could not fetch move {move_name}: {e}")
                    if move_objs:
                        pokemon.moves = move_objs
                # Set EVs (Effort Values)
                if evs:
                    total_evs = 0
                    for stat, value in evs.items():
                        if stat in ["hp", "attack", "defense", "sp_attack", "sp_defense", "speed"]:
                            base_stat = getattr(pokemon, stat)
                            ev_bonus = (value // 4)
                            setattr(pokemon, stat, base_stat + ev_bonus)
                            total_evs += value
                    print(f"[DEBUG] Applied EVs: {evs} (total: {total_evs})")
                # Set IVs (Individual Values) - for debugging, just print, as stats are already maxed
                if ivs:
                    print(f"[DEBUG] IVs: {ivs}")
                # Set item (already set in create_pokemon)
                if item:
                    print(f"[DEBUG] Item: {item}")
                # Set nature
                if nature:
                    print(f"[DEBUG] Nature: {nature}")
                # Set ability
                if ability:
                    print(f"[DEBUG] Ability: {ability}")
                print(f"[DEBUG] Moves: {moves}")
                print(f"Selected: {pokemon.name}")
                # Ask if user wants to override
                if is_player:
                    override = prompt("Override with manual customization? (y/n): ").strip().lower()
                    if override == "y":
                        pokemon = self.customize_pokemon(pokemon)
                # Reset move lock if present
                if hasattr(pokemon, 'locked_move'):
                    pokemon.locked_move = None
                return pokemon
            except requests.HTTPError:
                print("Pokémon not found on PokéAPI. Please try again.")
            except Exception as e:
                print(f"Error: {str(e)}")

    
    def start_battle(self):
            """Start a new battle"""
            print("🌟 Welcome to Pokemon Battle Simulator! 🌟")
            print("="*50)
            
            # Select Pokemon
            self.player_pokemon = self.select_pokemon(True)
            self.opponent_pokemon = self.select_pokemon(False)
            
            # Start battle
            self.battle_loop()
            
            # Ask for another battle
            while True:
                again = input("\nWould you like to battle again? (y/n): ").lower()
                if again in ['y', 'yes']:
                    self.start_battle()
                    break
                elif again in ['n', 'no']:
                    print("Thanks for playing! Goodbye!")
                    break
                else:
                    print("Please enter 'y' or 'n'")

def main():
    """Main function to run the battle simulator"""
    try:
        simulator = BattleSimulator()
        simulator.start_battle()
    except KeyboardInterrupt:
        print("\n\nBattle interrupted! Thanks for playing!")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
