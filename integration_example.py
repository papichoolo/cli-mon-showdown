"""
Integration Example: How to enhance your existing cli.py with the new battle system
This shows practical modifications to your current code
"""

import random
from typing import Dict, List, Optional, Any
from enhanced_battle_system import (
    EffectManager, BattleEvent, AbilityFactory, ItemFactory, 
    MegaEvolution, ReflectEffect, LightScreenEffect, SubstituteEffect
)

# Extend your existing Pokemon class
class EnhancedPokemon:
    """Enhanced Pokemon with mega evolution support"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add mega evolution tracking
        self.mega_evolved = False
        self.original_species = None
        self.original_base_stats = None
        self.original_types = None
        self.original_ability = None
        
        # Add IVs and EVs for proper stat calculation
        self.ivs = {stat: 31 for stat in ['hp', 'attack', 'defense', 'sp_attack', 'sp_defense', 'speed']}
        self.evs = {stat: 0 for stat in ['hp', 'attack', 'defense', 'sp_attack', 'sp_defense', 'speed']}
    
    def recalculate_stats(self):
        """Recalculate stats after mega evolution or other changes"""
        for stat, base_value in self.base_stats.items():
            if stat == 'hp':
                old_hp_percent = self.hp / self.max_hp if self.max_hp > 0 else 1
                self.max_hp = ((2 * base_value + self.ivs[stat] + self.evs[stat] // 4) * self.level // 100) + self.level + 10
                self.hp = int(self.max_hp * old_hp_percent)  # Maintain HP percentage
            else:
                stat_value = ((2 * base_value + self.ivs[stat] + self.evs[stat] // 4) * self.level // 100) + 5
                # Apply nature
                if hasattr(self, 'nature') and self.nature in NATURES:
                    nature_data = NATURES[self.nature]
                    if nature_data['increased'] == stat:
                        stat_value = int(stat_value * 1.1)
                    elif nature_data['decreased'] == stat:
                        stat_value = int(stat_value * 0.9)
                setattr(self, stat, stat_value)

class EnhancedBattleSimulator:
    """Enhanced version of your BattleSimulator"""
    
    def __init__(self):
        # Initialize your existing attributes
        self.player_pokemon = None
        self.opponent_pokemon = None
        self.battlefield = None
        
        # Add enhanced battle system
        self.effect_manager = EffectManager()
        self.mega_evolved = {'player': False, 'opponent': False}
        self.battle_messages = []
    
    def get_opponent_pokemon(self, pokemon):
        """Helper to get the opponent of a given pokemon"""
        if pokemon == self.player_pokemon:
            return self.opponent_pokemon
        return self.player_pokemon
    
    def initialize_pokemon_effects(self, pokemon):
        """Initialize effects for a Pokemon when it enters battle"""
        # Add ability effect
        ability_effect = AbilityFactory.create_ability(pokemon.ability.name, pokemon)
        self.effect_manager.add_effect(ability_effect)
        
        # Add item effect if present
        if pokemon.item:
            item_effect = ItemFactory.create_item_effect(pokemon.item.name, pokemon)
            if item_effect:
                self.effect_manager.add_effect(item_effect)
        
        # Trigger switch-in effects
        context = {'pokemon': pokemon, 'battle': self}
        results = self.effect_manager.trigger_event(BattleEvent.ON_SWITCH_IN, context)
        for result in results:
            if isinstance(result, str):
                print(result)
    
    def can_mega_evolve(self, pokemon) -> bool:
        """Check if Pokemon can mega evolve this battle"""
        player_key = 'player' if pokemon == self.player_pokemon else 'opponent'
        return (not self.mega_evolved[player_key] and 
                MegaEvolution.can_mega_evolve(pokemon))
    
    def mega_evolve_pokemon(self, pokemon) -> bool:
        """Perform mega evolution"""
        if not self.can_mega_evolve(pokemon):
            return False
        
        player_key = 'player' if pokemon == self.player_pokemon else 'opponent'
        
        # Remove old ability effect
        self.effect_manager.remove_effect(pokemon.ability.name)
        
        # Perform mega evolution
        if MegaEvolution.mega_evolve(pokemon):
            self.mega_evolved[player_key] = True
            
            # Add new ability effect
            ability_effect = AbilityFactory.create_ability(pokemon.ability.name, pokemon)
            self.effect_manager.add_effect(ability_effect)
            
            return True
        return False
    
    def calculate_enhanced_damage(self, attacker, defender, move) -> int:
        """Enhanced damage calculation with all battle effects"""
        if move.power == 0:
            return 0
        
        # Base calculations (your existing logic)
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
        
        # Base power modifications from abilities/items
        base_power = move.power
        context = {
            'move': move, 'attacker': attacker, 'defender': defender, 
            'base_power': base_power, 'battle': self
        }
        
        power_modifications = self.effect_manager.trigger_event(BattleEvent.MODIFY_BASE_POWER, context)
        for mod in power_modifications:
            if isinstance(mod, (int, float)):
                base_power = mod
                break  # Take first modification
        
        # Calculate base damage
        damage = ((2 * level / 5 + 2) * base_power * attack_stat / defense_stat) / 50 + 2
        
        # Type effectiveness
        type_mod = self.get_type_effectiveness(move.type, defender.types)
        damage *= type_mod
        
        # STAB (Same Type Attack Bonus)
        if move.type in attacker.types:
            damage *= 1.5
        
        # Weather effects
        if hasattr(self.battlefield, 'weather'):
            damage = self.apply_weather_damage_effects(damage, move, self.battlefield.weather)
        
        # Random factor (85-100%)
        damage *= random.randint(85, 100) / 100
        
        # Damage modifications from abilities/items
        context.update({'damage': damage, 'type_effectiveness': type_mod})
        damage_modifications = self.effect_manager.trigger_event(BattleEvent.MODIFY_DAMAGE, context)
        
        for mod in damage_modifications:
            if isinstance(mod, (int, float)):
                damage = mod
                break
        
        return max(1, int(damage))
    
    def execute_enhanced_move(self, attacker, defender, move, mega_evolve=False):
        """Enhanced move execution with full battle effects"""
        
        # Mega evolve before move if requested
        if mega_evolve:
            self.mega_evolve_pokemon(attacker)
        
        # Check for status conditions that prevent moves
        if not self.can_execute_move(attacker, move):
            return
        
        # Trigger before move effects
        context = {'attacker': attacker, 'defender': defender, 'move': move, 'battle': self}
        before_results = self.effect_manager.trigger_event(BattleEvent.BEFORE_MOVE, context)
        
        # Handle different move categories
        if move.category in ['Physical', 'Special']:
            self.execute_damaging_move(attacker, defender, move)
        else:
            self.execute_status_move_enhanced(attacker, defender, move)
        
        # Trigger after move effects
        after_results = self.effect_manager.trigger_event(BattleEvent.AFTER_MOVE, context)
        
        # Handle contact moves
        if hasattr(move, 'contact') and move.contact:
            from enhanced_battle_system import ContactMoveEffect
            contact_effect = ContactMoveEffect(defender)
            contact_results = contact_effect.trigger(BattleEvent.AFTER_MOVE, context)
            if contact_results:
                print(contact_results)
        
        # Print any effect messages
        for result in before_results + after_results:
            if isinstance(result, str):
                print(result)
    
    def execute_damaging_move(self, attacker, defender, move):
        """Execute a damaging move with enhanced effects"""
        # Calculate damage
        damage = self.calculate_enhanced_damage(attacker, defender, move)
        
        # Apply damage with defensive effects
        context = {
            'attacker': attacker, 'defender': defender, 'move': move,
            'damage': damage, 'battle': self
        }
        
        # Check for damage-taking effects (Focus Sash, Substitute, etc.)
        damage_taken_effects = self.effect_manager.trigger_event(BattleEvent.ON_DAMAGE_TAKEN, context)
        
        final_damage = damage
        for effect in damage_taken_effects:
            if isinstance(effect, int):
                final_damage = effect
                break
        
        # Apply damage
        defender.hp = max(0, defender.hp - final_damage)
        
        if final_damage > 0:
            print(f"{attacker.name} used {move.name}! {defender.name} took {final_damage} damage!")
        
        # Apply secondary effects
        self.apply_secondary_effects(attacker, defender, move)
        
        # Trigger damage events
        if final_damage > 0:
            damage_context = context.copy()
            damage_context['final_damage'] = final_damage
            self.effect_manager.trigger_event(BattleEvent.ON_DAMAGE, damage_context)
    
    def execute_status_move_enhanced(self, attacker, defender, move):
        """Enhanced status move execution"""
        target = defender if move.name not in ['Swords Dance', 'Calm Mind', 'Agility'] else attacker
        
        # Special status moves with effects
        if move.name == 'Reflect':
            team_side = 'player' if attacker == self.player_pokemon else 'opponent'
            reflect_effect = ReflectEffect(team_side)
            self.effect_manager.add_effect(reflect_effect)
            print(f"{attacker.name} used Reflect! Physical damage will be reduced!")
        
        elif move.name == 'Light Screen':
            team_side = 'player' if attacker == self.player_pokemon else 'opponent'
            light_screen_effect = LightScreenEffect(team_side)
            self.effect_manager.add_effect(light_screen_effect)
            print(f"{attacker.name} used Light Screen! Special damage will be reduced!")
        
        elif move.name == 'Substitute':
            substitute_cost = attacker.max_hp // 4
            if attacker.hp > substitute_cost:
                attacker.hp -= substitute_cost
                substitute_effect = SubstituteEffect(attacker, substitute_cost)
                self.effect_manager.add_effect(substitute_effect)
                print(f"{attacker.name} created a substitute!")
            else:
                print(f"{attacker.name} doesn't have enough HP for a substitute!")
        
        else:
            # Use your existing status move logic
            self.execute_status_move(attacker, target, move)
    
    def can_execute_move(self, pokemon, move) -> bool:
        """Check if Pokemon can execute the move (status conditions, etc.)"""
        # Sleep check
        if pokemon.status == StatusCondition.SLEEP:
            if pokemon.sleep_turns > 0:
                pokemon.sleep_turns -= 1
                print(f"{pokemon.name} is fast asleep!")
                if pokemon.sleep_turns == 0:
                    pokemon.status = StatusCondition.NONE
                    print(f"{pokemon.name} woke up!")
                return False
        
        # Paralysis check
        if pokemon.status == StatusCondition.PARALYSIS:
            if random.randint(1, 4) == 1:
                print(f"{pokemon.name} is paralyzed and can't move!")
                return False
        
        # Freeze check
        if pokemon.status == StatusCondition.FREEZE:
            if random.randint(1, 5) == 1:
                pokemon.status = StatusCondition.NONE
                print(f"{pokemon.name} thawed out!")
            else:
                print(f"{pokemon.name} is frozen solid!")
                return False
        
        # Flinch check
        if VolatileStatus.FLINCH in pokemon.volatile_status:
            pokemon.volatile_status.remove(VolatileStatus.FLINCH)
            print(f"{pokemon.name} flinched and couldn't move!")
            return False
        
        return True
    
    def apply_weather_damage_effects(self, damage, move, weather):
        """Apply weather effects to damage"""
        if weather == Weather.HARSH_SUNLIGHT:
            if move.type == 'Fire':
                damage *= 1.5
            elif move.type == 'Water':
                damage *= 0.5
        elif weather == Weather.RAIN:
            if move.type == 'Water':
                damage *= 1.5
            elif move.type == 'Fire':
                damage *= 0.5
        
        return damage
    
    def end_turn_effects_enhanced(self):
        """Enhanced end of turn processing"""
        # Your existing end turn effects
        self.end_turn_effects()
        
        # Process effect manager
        self.effect_manager.end_turn()
        
        # Trigger end of turn events for each Pokemon
        for pokemon in [self.player_pokemon, self.opponent_pokemon]:
            if pokemon and pokemon.hp > 0:
                context = {'pokemon': pokemon, 'battle': self}
                results = self.effect_manager.trigger_event(BattleEvent.END_OF_TURN, context)
                for result in results:
                    if isinstance(result, str):
                        print(result)
    
    def get_battle_actions(self, pokemon):
        """Get available actions including mega evolution"""
        actions = []
        
        # Regular moves
        for i, move in enumerate(pokemon.moves):
            action_text = f"{i+1}. {move.name}"
            if self.can_mega_evolve(pokemon):
                action_text += " (Can Mega Evolve)"
            actions.append(action_text)
        
        # Items (if any)
        if hasattr(pokemon, 'bag') and pokemon.bag:
            actions.append(f"{len(pokemon.moves)+1}. Use Item")
        
        # Switch (in future implementations)
        # actions.append(f"{len(actions)+1}. Switch Pokemon")
        
        return actions
    
    def handle_battle_turn(self):
        """Enhanced battle turn handling"""
        # Get player action
        print(f"\n{self.player_pokemon.name}'s turn!")
        actions = self.get_battle_actions(self.player_pokemon)
        
        for action in actions:
            print(action)
        
        try:
            choice = int(input("Choose an action: ")) - 1
            if 0 <= choice < len(self.player_pokemon.moves):
                player_move = self.player_pokemon.moves[choice]
                
                # Check for mega evolution
                mega_evolve = False
                if self.can_mega_evolve(self.player_pokemon):
                    mega_choice = input("Mega evolve? (y/n): ").lower()
                    mega_evolve = mega_choice == 'y'
                
                # AI opponent move selection (simple)
                opponent_move = random.choice(self.opponent_pokemon.moves)
                
                # Determine move order (considering Trick Room, priority, etc.)
                first_pokemon, first_move, first_mega = self.determine_move_order(
                    (self.player_pokemon, player_move, mega_evolve),
                    (self.opponent_pokemon, opponent_move, False)
                )
                
                # Execute moves
                if first_pokemon == self.player_pokemon:
                    self.execute_enhanced_move(self.player_pokemon, self.opponent_pokemon, first_move, first_mega)
                    if self.opponent_pokemon.hp > 0:
                        self.execute_enhanced_move(self.opponent_pokemon, self.player_pokemon, opponent_move, False)
                else:
                    self.execute_enhanced_move(self.opponent_pokemon, self.player_pokemon, opponent_move, False)
                    if self.player_pokemon.hp > 0:
                        self.execute_enhanced_move(self.player_pokemon, self.opponent_pokemon, player_move, mega_evolve)
                
                # End of turn effects
                self.end_turn_effects_enhanced()
                
        except (ValueError, IndexError):
            print("Invalid choice! Try again.")
            self.handle_battle_turn()
    
    def determine_move_order(self, action1, action2):
        """Determine which Pokemon moves first"""
        pokemon1, move1, mega1 = action1
        pokemon2, move2, mega2 = action2
        
        # Priority moves go first
        if move1.priority != move2.priority:
            if move1.priority > move2.priority:
                return pokemon1, move1, mega1
            else:
                return pokemon2, move2, mega2
        
        # Check for Trick Room effect
        trick_room_active = any(effect.name == "Trick Room" and effect.active 
                              for effect in self.effect_manager.effects)
        
        # Speed comparison (reverse if Trick Room is active)
        speed1 = pokemon1.speed * pokemon1.stat_changes.get_multiplier('speed')
        speed2 = pokemon2.speed * pokemon2.stat_changes.get_multiplier('speed')
        
        if trick_room_active:
            speed1, speed2 = speed2, speed1
        
        if speed1 > speed2:
            return pokemon1, move1, mega1
        elif speed2 > speed1:
            return pokemon2, move2, mega2
        else:
            # Speed tie - random
            if random.choice([True, False]):
                return pokemon1, move1, mega1
            else:
                return pokemon2, move2, mega2

# Example of how to use the enhanced system
def example_enhanced_battle():
    """Example of using the enhanced battle system"""
    
    # Create enhanced Pokemon (you would integrate this into your existing Pokemon creation)
    from cli import POKEMON_DATA, ITEMS
    
    # Player Pokemon with mega stone
    player_pokemon = EnhancedPokemon(
        name="Alakazam",
        species="Alakazam", 
        level=50,
        types=['Psychic'],
        base_stats={'hp': 55, 'attack': 50, 'defense': 45, 'sp_attack': 135, 'sp_defense': 95, 'speed': 120},
        moves=[
            Move('Psychic', 'Psychic', 'Special', 90, 100, 10, 10),
            Move('Shadow Ball', 'Ghost', 'Special', 80, 100, 15, 15),
            Move('Focus Blast', 'Fighting', 'Special', 120, 70, 5, 5),
            Move('Calm Mind', 'Psychic', 'Status', 0, 100, 20, 20),
        ],
        ability=Ability('Synchronize', 'Passes status conditions', 'status'),
        item=Item('Alakazite', 'Allows Alakazam to mega evolve', 'mega_stone'),
        nature="Modest"
    )
    
    # Opponent Pokemon
    opponent_pokemon = EnhancedPokemon(
        name="Garchomp",
        species="Garchomp",
        level=50,
        types=['Dragon', 'Ground'],
        base_stats={'hp': 108, 'attack': 130, 'defense': 95, 'sp_attack': 80, 'sp_defense': 85, 'speed': 102},
        moves=[
            Move('Earthquake', 'Ground', 'Physical', 100, 100, 10, 10),
            Move('Dragon Claw', 'Dragon', 'Physical', 80, 100, 15, 15),
            Move('Fire Fang', 'Fire', 'Physical', 65, 95, 15, 15),
            Move('Swords Dance', 'Normal', 'Status', 0, 100, 20, 20),
        ],
        ability=Ability('Rough Skin', 'Damages contact moves', 'contact_damage'),
        item=Item('Life Orb', 'Boosts move power but causes recoil', 'damage_boost'),
        nature="Jolly"
    )
    
    # Create enhanced battle simulator
    battle = EnhancedBattleSimulator()
    battle.player_pokemon = player_pokemon
    battle.opponent_pokemon = opponent_pokemon
    
    # Initialize Pokemon effects
    battle.initialize_pokemon_effects(player_pokemon)
    battle.initialize_pokemon_effects(opponent_pokemon)
    
    print("Enhanced Battle System Example")
    print(f"Player: {player_pokemon.name} (Can Mega Evolve: {battle.can_mega_evolve(player_pokemon)})")
    print(f"Opponent: {opponent_pokemon.name}")
    print("\nBattle begins!")
    
    # Example turn
    battle.handle_battle_turn()

if __name__ == "__main__":
    print("Enhanced Battle System Integration Example")
    print("This shows how to modify your existing cli.py with the new system")
