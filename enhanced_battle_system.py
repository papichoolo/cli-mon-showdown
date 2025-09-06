"""
Enhanced Battle Effects System
Practical implementation example for integrating comprehensive battle mechanics
"""

from typing import Dict, List, Callable, Any, Optional
from enum import Enum
from dataclasses import dataclass, field
import random

# Import your existing classes
from cli import Pokemon, Move, Ability, Item, StatusCondition, VolatileStatus

class BattleEvent(Enum):
    """Battle events that can trigger effects"""
    ON_SWITCH_IN = "on_switch_in"
    ON_SWITCH_OUT = "on_switch_out"
    BEFORE_MOVE = "before_move"
    AFTER_MOVE = "after_move"
    ON_DAMAGE = "on_damage"
    ON_DAMAGE_TAKEN = "on_damage_taken"
    MODIFY_DAMAGE = "modify_damage"
    MODIFY_BASE_POWER = "modify_base_power"
    MODIFY_ACCURACY = "modify_accuracy"
    ON_STATUS_INFLICT = "on_status_inflict"
    END_OF_TURN = "end_of_turn"
    ON_FAINT = "on_faint"
    ON_HEAL = "on_heal"

class BattleEffect:
    """Base class for all battle effects"""
    def __init__(self, name: str, duration: int = -1, priority: int = 0):
        self.name = name
        self.duration = duration  # -1 for permanent
        self.active = True
        self.priority = priority  # Higher priority effects trigger first
    
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        """Override in subclasses to handle specific events"""
        return None
    
    def tick(self):
        """Called each turn for duration tracking"""
        if self.duration > 0:
            self.duration -= 1
            if self.duration == 0:
                self.active = False

class EffectManager:
    """Manages all active battle effects"""
    def __init__(self):
        self.effects: List[BattleEffect] = []
    
    def add_effect(self, effect: BattleEffect):
        self.effects.append(effect)
        # Sort by priority
        self.effects.sort(key=lambda x: x.priority, reverse=True)
    
    def remove_effect(self, effect_name: str):
        self.effects = [e for e in self.effects if e.name != effect_name]
    
    def trigger_event(self, event: BattleEvent, context: Dict[str, Any]) -> List[Any]:
        """Trigger all effects for a given event"""
        results = []
        for effect in self.effects:
            if effect.active:
                result = effect.trigger(event, context)
                if result is not None:
                    results.append(result)
        return results
    
    def end_turn(self):
        """End of turn processing"""
        for effect in self.effects:
            effect.tick()
        self.effects = [e for e in self.effects if e.active]

# ============ ABILITY IMPLEMENTATIONS ============

class AbilityEffect(BattleEffect):
    """Base class for abilities"""
    def __init__(self, name: str, pokemon: Pokemon):
        super().__init__(name, -1)  # Abilities are permanent
        self.pokemon = pokemon

class IntimidateAbility(AbilityEffect):
    """Intimidate: Lowers opponent's Attack on switch-in"""
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if event == BattleEvent.ON_SWITCH_IN and context.get('pokemon') == self.pokemon:
            battle = context.get('battle')
            if battle:
                opponent = battle.get_opponent_pokemon(self.pokemon)
                if opponent and opponent.hp > 0:
                    opponent.stat_changes.attack = max(-6, opponent.stat_changes.attack - 1)
                    return f"{opponent.name}'s Attack was lowered by {self.pokemon.name}'s Intimidate!"

class TechnicianAbility(AbilityEffect):
    """Technician: Boosts moves with 60 BP or less by 50%"""
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if (event == BattleEvent.MODIFY_BASE_POWER and 
            context.get('attacker') == self.pokemon):
            move = context.get('move')
            if move and 0 < move.power <= 60:
                current_power = context.get('base_power', move.power)
                return current_power * 1.5

class SpeedBoostAbility(AbilityEffect):
    """Speed Boost: Raises Speed at end of turn"""
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if (event == BattleEvent.END_OF_TURN and 
            context.get('pokemon') == self.pokemon and 
            self.pokemon.hp > 0):
            self.pokemon.stat_changes.speed = min(6, self.pokemon.stat_changes.speed + 1)
            return f"{self.pokemon.name}'s Speed rose due to Speed Boost!"

class DroughtAbility(AbilityEffect):
    """Drought: Sets harsh sunlight on switch-in"""
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if event == BattleEvent.ON_SWITCH_IN and context.get('pokemon') == self.pokemon:
            battle = context.get('battle')
            if battle:
                from cli import Weather  # Import your Weather enum
                battle.battlefield.weather = Weather.HARSH_SUNLIGHT
                battle.battlefield.weather_turns = 5
                return f"{self.pokemon.name}'s Drought created harsh sunlight!"

# ============ ITEM IMPLEMENTATIONS ============

class ItemEffect(BattleEffect):
    """Base class for item effects"""
    def __init__(self, name: str, pokemon: Pokemon):
        super().__init__(name, -1)
        self.pokemon = pokemon
        self.consumed = False

class ChoiceBandItem(ItemEffect):
    """Choice Band: +50% Attack but locks into first move"""
    def __init__(self, pokemon: Pokemon):
        super().__init__("Choice Band", pokemon)
        self.locked_move = None
    
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if (event == BattleEvent.MODIFY_DAMAGE and 
            context.get('attacker') == self.pokemon):
            move = context.get('move')
            if move and move.category == 'Physical':
                damage = context.get('damage', 0)
                return damage * 1.5
        elif (event == BattleEvent.AFTER_MOVE and 
              context.get('attacker') == self.pokemon):
            move = context.get('move')
            if move and not self.locked_move:
                self.locked_move = move
                return f"{self.pokemon.name} is locked into {move.name}!"

class LifeOrbItem(ItemEffect):
    """Life Orb: +30% damage but 10% recoil on damaging moves"""
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if (event == BattleEvent.MODIFY_DAMAGE and 
            context.get('attacker') == self.pokemon):
            move = context.get('move')
            if move and move.category in ['Physical', 'Special'] and move.power > 0:
                damage = context.get('damage', 0)
                return damage * 1.3
        elif (event == BattleEvent.AFTER_MOVE and 
              context.get('attacker') == self.pokemon):
            move = context.get('move')
            if move and move.category in ['Physical', 'Special'] and move.power > 0:
                recoil = self.pokemon.max_hp // 10
                self.pokemon.hp = max(0, self.pokemon.hp - recoil)
                return f"{self.pokemon.name} is hurt by Life Orb! (-{recoil} HP)"

class FocusSashItem(ItemEffect):
    """Focus Sash: Survive lethal damage when at full HP"""
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if (event == BattleEvent.ON_DAMAGE_TAKEN and 
            context.get('defender') == self.pokemon and 
            not self.consumed):
            damage = context.get('damage', 0)
            if (self.pokemon.hp == self.pokemon.max_hp and 
                damage >= self.pokemon.hp):
                self.consumed = True
                return 1  # Return 1 to indicate survival with 1 HP

class WeaknessPolicy(ItemEffect):
    """Weakness Policy: +2 Attack and Sp. Attack when hit by super effective move"""
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if (event == BattleEvent.ON_DAMAGE_TAKEN and 
            context.get('defender') == self.pokemon and 
            not self.consumed):
            type_effectiveness = context.get('type_effectiveness', 1.0)
            if type_effectiveness > 1.0:  # Super effective
                self.consumed = True
                self.pokemon.stat_changes.attack = min(6, self.pokemon.stat_changes.attack + 2)
                self.pokemon.stat_changes.sp_attack = min(6, self.pokemon.stat_changes.sp_attack + 2)
                return f"{self.pokemon.name}'s Weakness Policy activated! Attack and Sp. Attack rose sharply!"

# ============ MOVE EFFECTS ============

class MoveEffect(BattleEffect):
    """Base class for move effects"""
    def __init__(self, name: str, duration: int = 1):
        super().__init__(name, duration)

class ReflectEffect(BattleEffect):
    """Reflect: Halves physical damage for 5 turns"""
    def __init__(self, team_side: str):
        super().__init__("Reflect", 5)
        self.team_side = team_side
    
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if event == BattleEvent.MODIFY_DAMAGE:
            defender = context.get('defender')
            move = context.get('move')
            battle = context.get('battle')
            
            # Check if defender is on the protected side
            if (move and move.category == 'Physical' and
                ((self.team_side == 'player' and defender == battle.player_pokemon) or
                 (self.team_side == 'opponent' and defender == battle.opponent_pokemon))):
                damage = context.get('damage', 0)
                return damage * 0.5

class LightScreenEffect(BattleEffect):
    """Light Screen: Halves special damage for 5 turns"""
    def __init__(self, team_side: str):
        super().__init__("Light Screen", 5)
        self.team_side = team_side
    
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if event == BattleEvent.MODIFY_DAMAGE:
            defender = context.get('defender')
            move = context.get('move')
            battle = context.get('battle')
            
            if (move and move.category == 'Special' and
                ((self.team_side == 'player' and defender == battle.player_pokemon) or
                 (self.team_side == 'opponent' and defender == battle.opponent_pokemon))):
                damage = context.get('damage', 0)
                return damage * 0.5

class TrickRoomEffect(BattleEffect):
    """Trick Room: Reverses speed priority for 5 turns"""
    def __init__(self):
        super().__init__("Trick Room", 5)
        self.active_room = True

class SubstituteEffect(BattleEffect):
    """Substitute: Blocks most moves and status conditions"""
    def __init__(self, pokemon: Pokemon, substitute_hp: int):
        super().__init__(f"Substitute-{pokemon.name}", -1)
        self.pokemon = pokemon
        self.substitute_hp = substitute_hp
    
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if (event == BattleEvent.ON_DAMAGE_TAKEN and 
            context.get('defender') == self.pokemon):
            damage = context.get('damage', 0)
            move = context.get('move')
            
            # Some moves bypass substitute
            if move and move.name in ['Seismic Toss', 'Night Shade']:
                return None
            
            if self.substitute_hp > 0:
                actual_damage = min(damage, self.substitute_hp)
                self.substitute_hp -= actual_damage
                
                if self.substitute_hp <= 0:
                    self.active = False
                    return f"{self.pokemon.name}'s substitute broke!"
                return 0  # No damage to the actual Pokemon

# ============ FACTORY CLASSES ============

class AbilityFactory:
    """Factory to create abilities"""
    ABILITY_MAP = {
        'Intimidate': IntimidateAbility,
        'Technician': TechnicianAbility,
        'Speed Boost': SpeedBoostAbility,
        'Drought': DroughtAbility,
    }
    
    @staticmethod
    def create_ability(name: str, pokemon: Pokemon) -> AbilityEffect:
        ability_class = AbilityFactory.ABILITY_MAP.get(name)
        if ability_class:
            return ability_class(pokemon)
        return AbilityEffect(name, pokemon)  # Default fallback

class ItemFactory:
    """Factory to create item effects"""
    ITEM_MAP = {
        'Choice Band': ChoiceBandItem,
        'Life Orb': LifeOrbItem,
        'Focus Sash': FocusSashItem,
        'Weakness Policy': WeaknessPolicy,
    }
    
    @staticmethod
    def create_item_effect(item_name: str, pokemon: Pokemon) -> Optional[ItemEffect]:
        item_class = ItemFactory.ITEM_MAP.get(item_name)
        if item_class:
            return item_class(pokemon)
        return None

# ============ MEGA EVOLUTION SYSTEM ============

@dataclass
class MegaStone:
    name: str
    pokemon_species: str
    mega_forme: str
    
class MegaEvolution:
    """Handles mega evolution mechanics"""
    
    MEGA_STONES = {
        'Alakazite': MegaStone('Alakazite', 'Alakazam', 'Alakazam-Mega'),
        'Charizardite X': MegaStone('Charizardite X', 'Charizard', 'Charizard-Mega-X'),
        'Charizardite Y': MegaStone('Charizardite Y', 'Charizard', 'Charizard-Mega-Y'),
        'Gengarite': MegaStone('Gengarite', 'Gengar', 'Gengar-Mega'),
        'Kangaskhanite': MegaStone('Kangaskhanite', 'Kangaskhan', 'Kangaskhan-Mega'),
    }
    
    MEGA_STATS = {
        'Alakazam-Mega': {'hp': 55, 'attack': 50, 'defense': 65, 'sp_attack': 175, 'sp_defense': 105, 'speed': 150},
        'Charizard-Mega-X': {'hp': 78, 'attack': 130, 'defense': 111, 'sp_attack': 130, 'sp_defense': 85, 'speed': 100},
        'Charizard-Mega-Y': {'hp': 78, 'attack': 104, 'defense': 78, 'sp_attack': 159, 'sp_defense': 115, 'speed': 100},
        'Gengar-Mega': {'hp': 60, 'attack': 65, 'defense': 80, 'sp_attack': 170, 'sp_defense': 95, 'speed': 130},
        'Kangaskhan-Mega': {'hp': 105, 'attack': 125, 'defense': 100, 'sp_attack': 60, 'sp_defense': 100, 'speed': 100},
    }
    
    MEGA_TYPES = {
        'Charizard-Mega-X': ['Fire', 'Dragon'],
        'Charizard-Mega-Y': ['Fire', 'Flying'],
    }
    
    MEGA_ABILITIES = {
        'Alakazam-Mega': Ability('Trace', 'Copies opponent ability', 'trace'),
        'Charizard-Mega-X': Ability('Tough Claws', 'Powers up contact moves', 'contact_boost'),
        'Charizard-Mega-Y': Ability('Drought', 'Summons harsh sunlight', 'weather'),
        'Gengar-Mega': Ability('Shadow Tag', 'Prevents opponent from switching', 'trap'),
        'Kangaskhan-Mega': Ability('Parental Bond', 'Attacks twice', 'multi_hit'),
    }
    
    @staticmethod
    def can_mega_evolve(pokemon: Pokemon) -> bool:
        """Check if Pokemon can mega evolve"""
        if not pokemon.item or pokemon.item.name not in MegaEvolution.MEGA_STONES:
            return False
        
        mega_stone = MegaEvolution.MEGA_STONES[pokemon.item.name]
        return mega_stone.pokemon_species == pokemon.species
    
    @staticmethod
    def mega_evolve(pokemon: Pokemon) -> bool:
        """Perform mega evolution"""
        if not MegaEvolution.can_mega_evolve(pokemon):
            return False
        
        mega_stone = MegaEvolution.MEGA_STONES[pokemon.item.name]
        
        # Store original data
        pokemon.original_species = pokemon.species
        pokemon.original_base_stats = pokemon.base_stats.copy()
        pokemon.original_types = pokemon.types.copy()
        pokemon.original_ability = pokemon.ability
        
        # Update to mega forme
        pokemon.species = mega_stone.mega_forme
        pokemon.mega_evolved = True
        
        # Update stats
        mega_stats = MegaEvolution.MEGA_STATS.get(mega_stone.mega_forme)
        if mega_stats:
            pokemon.base_stats = mega_stats
            pokemon.recalculate_stats()
        
        # Update types
        mega_types = MegaEvolution.MEGA_TYPES.get(mega_stone.mega_forme)
        if mega_types:
            pokemon.types = mega_types
        
        # Update ability
        mega_ability = MegaEvolution.MEGA_ABILITIES.get(mega_stone.mega_forme)
        if mega_ability:
            pokemon.ability = mega_ability
        
        print(f"{pokemon.original_species} mega evolved into {pokemon.species}!")
        return True

# ============ ENHANCED MOVE EFFECTS ============

class ContactMoveEffect(BattleEffect):
    """Handles contact move interactions (Rough Skin, Static, etc.)"""
    def __init__(self, defender: Pokemon):
        super().__init__(f"Contact-{defender.ability.name}", 1)
        self.defender = defender
    
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if event == BattleEvent.AFTER_MOVE:
            attacker = context.get('attacker')
            move = context.get('move')
            
            if move and move.contact and attacker:
                # Rough Skin / Iron Barbs
                if self.defender.ability.name in ['Rough Skin', 'Iron Barbs']:
                    damage = attacker.max_hp // 8
                    attacker.hp = max(0, attacker.hp - damage)
                    return f"{attacker.name} was hurt by {self.defender.name}'s {self.defender.ability.name}!"
                
                # Static / Flame Body / Poison Point
                elif self.defender.ability.name == 'Static' and random.randint(1, 100) <= 30:
                    if attacker.status == StatusCondition.NONE:
                        attacker.status = StatusCondition.PARALYSIS
                        return f"{attacker.name} was paralyzed by Static!"

# Example of how to integrate this into your existing BattleSimulator
def integrate_enhanced_effects():
    """
    Integration guide for your existing BattleSimulator class:
    
    1. Add EffectManager to __init__:
       self.effect_manager = EffectManager()
       self.mega_evolved = {'player': False, 'opponent': False}
    
    2. Initialize Pokemon effects when they switch in:
       # Add ability effect
       ability_effect = AbilityFactory.create_ability(pokemon.ability.name, pokemon)
       self.effect_manager.add_effect(ability_effect)
       
       # Add item effect if present
       if pokemon.item:
           item_effect = ItemFactory.create_item_effect(pokemon.item.name, pokemon)
           if item_effect:
               self.effect_manager.add_effect(item_effect)
    
    3. Modify calculate_damage to use effects:
       context = {
           'attacker': attacker, 'defender': defender, 'move': move,
           'base_power': move.power, 'damage': calculated_damage,
           'type_effectiveness': type_mod, 'battle': self
       }
       
       # Apply base power modifications
       power_mods = self.effect_manager.trigger_event(BattleEvent.MODIFY_BASE_POWER, context)
       for mod in power_mods:
           if isinstance(mod, (int, float)):
               move.power = mod
       
       # Apply damage modifications
       damage_mods = self.effect_manager.trigger_event(BattleEvent.MODIFY_DAMAGE, context)
       for mod in damage_mods:
           if isinstance(mod, (int, float)):
               damage = mod
    
    4. Add mega evolution option to battle loop:
       if can_mega_evolve(pokemon):
           # Add mega evolution option to move selection
           
    5. Update end_turn_effects:
       super().end_turn_effects()
       self.effect_manager.end_turn()
       
       for pokemon in [self.player_pokemon, self.opponent_pokemon]:
           if pokemon.hp > 0:
               context = {'pokemon': pokemon, 'battle': self}
               self.effect_manager.trigger_event(BattleEvent.END_OF_TURN, context)
    """
    pass

if __name__ == "__main__":
    # Example usage and testing
    print("Enhanced Battle Effects System loaded successfully!")
    print("See integrate_enhanced_effects() function for integration guide.")
