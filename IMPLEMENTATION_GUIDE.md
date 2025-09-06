# Complete Pokemon Battle Mechanics Implementation Guide

Based on analysis of the PokeChamp repository and your current CLI implementation, here's a comprehensive guide to implement complete support for moves, abilities, battle effects, items, and mega evolution.

## 1. Enhanced Battle Effects System

### Current State
Your implementation has basic secondary effects but lacks comprehensive battle effect handling.

### Implementation Pattern from PokeChamp
PokeChamp uses event-driven hooks like `onDamage`, `onBasePower`, `onModifyDamage`, `onAfterMove`, etc.

### Recommended Implementation

```python
from enum import Enum
from typing import Dict, List, Callable, Any

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

class BattleEffect:
    """Base class for all battle effects"""
    def __init__(self, name: str, duration: int = -1):
        self.name = name
        self.duration = duration  # -1 for permanent
        self.active = True
    
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        """Override in subclasses to handle specific events"""
        pass
    
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
```

## 2. Advanced Ability System

### Current State
Your abilities are basic with simple effect types.

### Enhanced Ability Implementation

```python
class AbilityEffect(BattleEffect):
    """Base class for abilities"""
    def __init__(self, name: str, pokemon: 'Pokemon'):
        super().__init__(name, -1)  # Abilities are permanent
        self.pokemon = pokemon

class IntimidateAbility(AbilityEffect):
    """Example: Intimidate lowers opponent's Attack on switch-in"""
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if event == BattleEvent.ON_SWITCH_IN:
            battle = context.get('battle')
            opponent = battle.get_opponent(self.pokemon)
            if opponent:
                opponent.stat_changes.attack = max(-6, opponent.stat_changes.attack - 1)
                return f"{opponent.name}'s Attack was lowered by {self.pokemon.name}'s Intimidate!"

class TechnicianAbility(AbilityEffect):
    """Example: Technician boosts moves with 60 BP or less"""
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if event == BattleEvent.MODIFY_BASE_POWER:
            move = context.get('move')
            if move and move.power <= 60 and move.power > 0:
                current_power = context.get('base_power', move.power)
                return current_power * 1.5

class AbilityFactory:
    """Factory to create abilities"""
    @staticmethod
    def create_ability(name: str, pokemon: 'Pokemon') -> AbilityEffect:
        ability_map = {
            'Intimidate': IntimidateAbility,
            'Technician': TechnicianAbility,
            # Add more abilities here
        }
        ability_class = ability_map.get(name)
        if ability_class:
            return ability_class(name, pokemon)
        return AbilityEffect(name, pokemon)  # Default fallback
```

## 3. Comprehensive Item System

### Current State
Your items have basic effects like healing and stat boosts.

### Enhanced Item Implementation

```python
class ItemEffect(BattleEffect):
    """Base class for item effects"""
    def __init__(self, name: str, pokemon: 'Pokemon'):
        super().__init__(name, -1)
        self.pokemon = pokemon
        self.consumed = False

class ChoiceBandItem(ItemEffect):
    """Choice Band: +50% Attack but locks into first move"""
    def __init__(self, pokemon: 'Pokemon'):
        super().__init__("Choice Band", pokemon)
        self.locked_move = None
    
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if event == BattleEvent.MODIFY_DAMAGE:
            move = context.get('move')
            if move and move.category == 'Physical':
                damage = context.get('damage', 0)
                return damage * 1.5
        elif event == BattleEvent.AFTER_MOVE:
            move = context.get('move')
            if move and not self.locked_move:
                self.locked_move = move
                return f"{self.pokemon.name} is locked into {move.name}!"

class LifeOrbItem(ItemEffect):
    """Life Orb: +30% damage but 10% recoil"""
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if event == BattleEvent.MODIFY_DAMAGE:
            move = context.get('move')
            if move and move.category in ['Physical', 'Special']:
                damage = context.get('damage', 0)
                return damage * 1.3
        elif event == BattleEvent.AFTER_MOVE:
            move = context.get('move')
            if move and move.category in ['Physical', 'Special']:
                recoil = self.pokemon.max_hp // 10
                self.pokemon.hp = max(0, self.pokemon.hp - recoil)
                return f"{self.pokemon.name} is hurt by Life Orb!"

class FocusSashItem(ItemEffect):
    """Focus Sash: Survive lethal damage at full HP"""
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if event == BattleEvent.ON_DAMAGE and not self.consumed:
            damage = context.get('damage', 0)
            if (self.pokemon.hp == self.pokemon.max_hp and 
                damage >= self.pokemon.hp):
                self.consumed = True
                return self.pokemon.hp - 1  # Survive with 1 HP

class TypeBoostingItem(ItemEffect):
    """Type-boosting items like Charcoal, Mystic Water, etc."""
    def __init__(self, pokemon: 'Pokemon', boosted_type: str):
        super().__init__(f"{boosted_type} Boost Item", pokemon)
        self.boosted_type = boosted_type
    
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if event == BattleEvent.MODIFY_BASE_POWER:
            move = context.get('move')
            if move and move.type == self.boosted_type:
                current_power = context.get('base_power', move.power)
                return current_power * 1.2  # 20% boost
```

## 4. Advanced Move Effects System

### Current State
Your moves have basic secondary effects.

### Enhanced Move Implementation

```python
class MoveEffect(BattleEffect):
    """Base class for move effects"""
    def __init__(self, name: str, move: 'Move'):
        super().__init__(name, 1)  # Most move effects last 1 turn
        self.move = move

class SubstituteEffect(BattleEffect):
    """Substitute effect"""
    def __init__(self, pokemon: 'Pokemon', hp_cost: int):
        super().__init__("Substitute", -1)
        self.pokemon = pokemon
        self.substitute_hp = hp_cost
    
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if event == BattleEvent.ON_DAMAGE_TAKEN:
            damage = context.get('damage', 0)
            if self.substitute_hp > 0:
                actual_damage = min(damage, self.substitute_hp)
                self.substitute_hp -= actual_damage
                if self.substitute_hp <= 0:
                    self.active = False
                    return f"{self.pokemon.name}'s substitute broke!"
                return f"The substitute took the damage!"

class ReflectEffect(BattleEffect):
    """Reflect: Halves physical damage for 5 turns"""
    def __init__(self):
        super().__init__("Reflect", 5)
    
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if event == BattleEvent.MODIFY_DAMAGE:
            move = context.get('move')
            if move and move.category == 'Physical':
                damage = context.get('damage', 0)
                return damage * 0.5

class TrickRoomEffect(BattleEffect):
    """Trick Room: Reverses speed priority for 5 turns"""
    def __init__(self):
        super().__init__("Trick Room", 5)
    
    def trigger(self, event: BattleEvent, context: Dict[str, Any]) -> Any:
        if event == BattleEvent.BEFORE_MOVE:
            # This would need integration with battle turn order logic
            pass

# Enhanced Move class
@dataclass
class EnhancedMove(Move):
    flags: Dict[str, bool] = field(default_factory=dict)  # contact, protect, etc.
    drain_percentage: float = 0  # For draining moves
    recoil_percentage: float = 0  # For recoil moves
    multi_hit: tuple = None  # (min, max) for multi-hit moves
    charge_turn: bool = False  # Requires charging
    
    def has_flag(self, flag: str) -> bool:
        return self.flags.get(flag, False)
```

## 5. Mega Evolution Implementation

### Based on PokeChamp Pattern

```python
@dataclass
class MegaStone:
    name: str
    pokemon_species: str  # Which Pokemon can use it
    mega_forme: str  # The mega evolution forme
    
class MegaEvolution:
    """Handles mega evolution mechanics"""
    
    MEGA_STONES = {
        'Alakazite': MegaStone('Alakazite', 'Alakazam', 'Alakazam-Mega'),
        'Charizardite X': MegaStone('Charizardite X', 'Charizard', 'Charizard-Mega-X'),
        'Charizardite Y': MegaStone('Charizardite Y', 'Charizard', 'Charizard-Mega-Y'),
        # Add more mega stones
    }
    
    @staticmethod
    def can_mega_evolve(pokemon: 'Pokemon') -> bool:
        """Check if Pokemon can mega evolve"""
        if not pokemon.item:
            return False
        
        mega_stone = MegaEvolution.MEGA_STONES.get(pokemon.item.name)
        if not mega_stone:
            return False
        
        return mega_stone.pokemon_species == pokemon.species
    
    @staticmethod
    def mega_evolve(pokemon: 'Pokemon', battle_simulator: 'BattleSimulator'):
        """Perform mega evolution"""
        if not MegaEvolution.can_mega_evolve(pokemon):
            return False
        
        mega_stone = MegaEvolution.MEGA_STONES[pokemon.item.name]
        
        # Store original stats for potential reversal
        pokemon.original_species = pokemon.species
        pokemon.original_base_stats = pokemon.base_stats.copy()
        
        # Update to mega forme
        pokemon.species = mega_stone.mega_forme
        
        # Update stats based on mega forme
        mega_stats = MegaEvolution.get_mega_stats(mega_stone.mega_forme)
        if mega_stats:
            pokemon.base_stats = mega_stats
            # Recalculate actual stats
            pokemon.recalculate_stats()
        
        # Update types if necessary
        mega_types = MegaEvolution.get_mega_types(mega_stone.mega_forme)
        if mega_types:
            pokemon.types = mega_types
        
        # Update ability
        mega_ability = MegaEvolution.get_mega_ability(mega_stone.mega_forme)
        if mega_ability:
            # Remove old ability effect
            battle_simulator.effect_manager.remove_effect(pokemon.ability.name)
            # Add new ability
            pokemon.ability = mega_ability
            new_ability_effect = AbilityFactory.create_ability(mega_ability.name, pokemon)
            battle_simulator.effect_manager.add_effect(new_ability_effect)
        
        print(f"{pokemon.original_species} mega evolved into {pokemon.species}!")
        return True
    
    @staticmethod
    def get_mega_stats(mega_forme: str) -> Dict[str, int]:
        """Get base stats for mega forme"""
        mega_stats_db = {
            'Alakazam-Mega': {'hp': 55, 'attack': 50, 'defense': 65, 'sp_attack': 175, 'sp_defense': 105, 'speed': 150},
            'Charizard-Mega-X': {'hp': 78, 'attack': 130, 'defense': 111, 'sp_attack': 130, 'sp_defense': 85, 'speed': 100},
            'Charizard-Mega-Y': {'hp': 78, 'attack': 104, 'defense': 78, 'sp_attack': 159, 'sp_defense': 115, 'speed': 100},
        }
        return mega_stats_db.get(mega_forme)
    
    @staticmethod
    def get_mega_types(mega_forme: str) -> List[str]:
        """Get types for mega forme"""
        mega_types_db = {
            'Charizard-Mega-X': ['Fire', 'Dragon'],
            'Charizard-Mega-Y': ['Fire', 'Flying'],
        }
        return mega_types_db.get(mega_forme)
    
    @staticmethod
    def get_mega_ability(mega_forme: str) -> 'Ability':
        """Get ability for mega forme"""
        mega_abilities_db = {
            'Alakazam-Mega': Ability('Trace', 'Copies opponent ability', 'trace'),
            'Charizard-Mega-X': Ability('Tough Claws', 'Powers up contact moves', 'contact_boost'),
            'Charizard-Mega-Y': Ability('Drought', 'Summons harsh sunlight', 'weather'),
        }
        return mega_abilities_db.get(mega_forme)

# Enhanced Pokemon class method
def recalculate_stats(self):
    """Recalculate stats based on base stats, level, nature, etc."""
    for stat, base_value in self.base_stats.items():
        if stat == 'hp':
            self.max_hp = ((2 * base_value + self.ivs.get(stat, 31) + self.evs.get(stat, 0) // 4) * self.level // 100) + self.level + 10
            if self.hp == 0:  # If first calculation
                self.hp = self.max_hp
        else:
            stat_value = ((2 * base_value + self.ivs.get(stat, 31) + self.evs.get(stat, 0) // 4) * self.level // 100) + 5
            # Apply nature
            if self.nature and NATURES.get(self.nature):
                nature_data = NATURES[self.nature]
                if nature_data['increased'] == stat:
                    stat_value = int(stat_value * 1.1)
                elif nature_data['decreased'] == stat:
                    stat_value = int(stat_value * 0.9)
            setattr(self, stat, stat_value)
```

## 6. Enhanced Battle Simulator Integration

### Updated BattleSimulator Class

```python
class EnhancedBattleSimulator(BattleSimulator):
    def __init__(self):
        super().__init__()
        self.effect_manager = EffectManager()
        self.mega_evolved = {'player': False, 'opponent': False}
    
    def can_mega_evolve(self, pokemon: Pokemon) -> bool:
        """Check if Pokemon can mega evolve this battle"""
        player_key = 'player' if pokemon == self.player_pokemon else 'opponent'
        return (not self.mega_evolved[player_key] and 
                MegaEvolution.can_mega_evolve(pokemon))
    
    def execute_move(self, attacker: Pokemon, defender: Pokemon, move: Move, mega_evolve: bool = False):
        """Enhanced move execution with mega evolution support"""
        
        # Mega evolve before move if requested
        if mega_evolve and self.can_mega_evolve(attacker):
            player_key = 'player' if attacker == self.player_pokemon else 'opponent'
            if MegaEvolution.mega_evolve(attacker, self):
                self.mega_evolved[player_key] = True
        
        # Trigger before move effects
        context = {'attacker': attacker, 'defender': defender, 'move': move, 'battle': self}
        self.effect_manager.trigger_event(BattleEvent.BEFORE_MOVE, context)
        
        # Execute move with enhanced damage calculation
        if move.category in ['Physical', 'Special']:
            damage = self.calculate_enhanced_damage(attacker, defender, move)
            
            # Apply damage with effects
            final_damage = self.apply_damage_effects(defender, damage, move, attacker)
            defender.hp = max(0, defender.hp - final_damage)
            
            print(f"{attacker.name} used {move.name}! {defender.name} took {final_damage} damage!")
            
            # Apply secondary effects
            self.apply_secondary_effects(attacker, defender, move)
        
        # Trigger after move effects
        context['damage'] = damage if 'damage' in locals() else 0
        self.effect_manager.trigger_event(BattleEvent.AFTER_MOVE, context)
    
    def calculate_enhanced_damage(self, attacker: Pokemon, defender: Pokemon, move: Move) -> int:
        """Enhanced damage calculation with ability and item effects"""
        if move.power == 0:
            return 0
        
        # Base damage calculation
        level = attacker.level
        attack_stat = attacker.attack if move.category == 'Physical' else attacker.sp_attack
        defense_stat = defender.defense if move.category == 'Physical' else defender.sp_defense
        
        # Apply stat changes
        attack_multiplier = attacker.stat_changes.get_multiplier(
            'attack' if move.category == 'Physical' else 'sp_attack'
        )
        defense_multiplier = defender.stat_changes.get_multiplier(
            'defense' if move.category == 'Physical' else 'sp_defense'
        )
        
        attack_stat = int(attack_stat * attack_multiplier)
        defense_stat = int(defense_stat * defense_multiplier)
        
        # Base power modifications
        base_power = move.power
        context = {'move': move, 'attacker': attacker, 'defender': defender, 'base_power': base_power}
        power_modifications = self.effect_manager.trigger_event(BattleEvent.MODIFY_BASE_POWER, context)
        
        for mod in power_modifications:
            if isinstance(mod, (int, float)):
                base_power = mod
        
        # Calculate base damage
        damage = ((2 * level / 5 + 2) * base_power * attack_stat / defense_stat) / 50 + 2
        
        # Type effectiveness
        type_mod = self.get_type_effectiveness(move.type, defender.types)
        damage *= type_mod
        
        # STAB (Same Type Attack Bonus)
        if move.type in attacker.types:
            damage *= 1.5
        
        # Random factor (85-100%)
        damage *= random.randint(85, 100) / 100
        
        # Damage modifications from effects
        context = {'move': move, 'attacker': attacker, 'defender': defender, 'damage': damage}
        damage_modifications = self.effect_manager.trigger_event(BattleEvent.MODIFY_DAMAGE, context)
        
        for mod in damage_modifications:
            if isinstance(mod, (int, float)):
                damage = mod
        
        return max(1, int(damage))
    
    def apply_damage_effects(self, defender: Pokemon, damage: int, move: Move, attacker: Pokemon) -> int:
        """Apply effects that modify incoming damage"""
        context = {
            'defender': defender,
            'damage': damage,
            'move': move,
            'attacker': attacker
        }
        
        damage_taken_effects = self.effect_manager.trigger_event(BattleEvent.ON_DAMAGE_TAKEN, context)
        
        final_damage = damage
        for effect_result in damage_taken_effects:
            if isinstance(effect_result, (int, float)):
                final_damage = effect_result
        
        return final_damage
    
    def end_turn_effects(self):
        """Enhanced end of turn processing"""
        super().end_turn_effects()
        
        # Process effect manager
        self.effect_manager.end_turn()
        
        # Trigger end of turn events
        for pokemon in [self.player_pokemon, self.opponent_pokemon]:
            if pokemon.hp > 0:
                context = {'pokemon': pokemon, 'battle': self}
                self.effect_manager.trigger_event(BattleEvent.END_OF_TURN, context)
```

## 7. Integration Steps

1. **Update Pokemon class** to support the enhanced stat calculation and mega evolution
2. **Replace Move class** with EnhancedMove for better effect handling
3. **Update Item class** to use the new ItemEffect system
4. **Replace Ability class** with the new AbilityEffect system
5. **Integrate EffectManager** into your battle simulator
6. **Add MegaEvolution support** to battle flow
7. **Update damage calculation** to use the event system
8. **Enhance status move execution** with the effect system

This implementation provides:
- Event-driven battle effects system
- Comprehensive ability interactions
- Complex item effects with proper timing
- Mega evolution with stat/type/ability changes
- Extensible framework for adding new moves/abilities/items
- Proper effect duration and timing management

The system is designed to be modular and easily extensible, following the patterns observed in PokeChamp while being adapted to your CLI-based implementation.
