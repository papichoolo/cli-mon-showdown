"""
Gemini API Agent for Pokemon Showdown Battle Decisions

This module provides an interface to Google's Gemini API for making strategic
Pokemon battle decisions based on game state observations.
"""

import json
import os
from typing import Dict, Optional, Tuple, Any, List, TypedDict, Literal
from pydantic import BaseModel, Field
import subprocess
import re
from dotenv import load_dotenv
import showdown_wrapper

# Load environment variables from .env file
load_dotenv()

# For Langchain OpenRouter as requested
try:
    from langchain.agents import create_agent
except ImportError:
    pass
from langchain_openrouter import ChatOpenRouter
from langchain_core.tools import tool

class OpponentKnowledge(TypedDict):
    active_pokemon: str
    team: Dict[str, dict]

class DecisionInput(BaseModel):
    """Input for submitting a battle decision."""
    action_type: Literal["move", "switch"] = Field(description="Either 'move' or 'switch'")
    choice: int = Field(description="Index of the move (1-4) or Pokemon slot (1-6)")
    reasoning: str = Field(description="Brief explanation of the choice")

@tool(args_schema=DecisionInput)
def submit_decision(action_type: str, choice: int, reasoning: str) -> str:
    """Submit your Pokemon battle decision for the current turn.
    action_type: Either 'move' or 'switch'.
    choice: Index of the move (1-4) or Pokemon slot (1-6).
    reasoning: Brief explanation of the choice.
    """
    return json.dumps({
        "action_type": action_type,
        "choice": choice,
        "reasoning": reasoning
    })

def update_tracker(raw_log: str, current_knowledge: dict) -> tuple[dict, str]:
    """Parses raw showdown log, updates opponent knowledge, and compacts the log."""
    compact_log = []
    
    for line in raw_log.split('\n'):
        if line.startswith('|move|p1a:'):
            parts = line.split('|')
            if len(parts) >= 4:
                pokemon_raw = parts[2].split(': ')[1] if ': ' in parts[2] else parts[2]
                move = parts[3]
                if pokemon_raw not in current_knowledge['team']:
                    current_knowledge['team'][pokemon_raw] = {"moves": set(), "item": "Unknown"}
                current_knowledge['team'][pokemon_raw]['moves'].add(move)
                compact_log.append(f"Opponent {pokemon_raw} used {move}.")
                
        elif line.startswith('|switch|p1a:') or line.startswith('|drag|p1a:'):
            parts = line.split('|')
            if len(parts) >= 4:
                pokemon_raw = parts[3].split(',')[0]
                current_knowledge['active_pokemon'] = pokemon_raw
                if pokemon_raw not in current_knowledge['team']:
                    current_knowledge['team'][pokemon_raw] = {"moves": set(), "item": "Unknown"}
                compact_log.append(f"Opponent switched to {pokemon_raw}.")
                
    return current_knowledge, "\n".join(compact_log)

class DamageCalcInput(BaseModel):
    """Input for damage calculation."""
    gen: int = Field(description="Generation number, usually 9")
    attacker_name: str = Field(description="Name of attacking Pokemon")
    defender_name: str = Field(description="Name of defending Pokemon")
    move_name: str = Field(description="Name of the move")

@tool(args_schema=DamageCalcInput)
def calculate_damage(gen: int, attacker_name: str, defender_name: str, move_name: str) -> str:
    """Calculates potential damage range for a given move."""
    payload = {
        "gen": gen,
        "attacker": {"name": attacker_name, "details": {}},
        "defender": {"name": defender_name, "details": {}},
        "move": move_name
    }
    
    result = subprocess.run(
        ['node', 'calc_wrapper.js', json.dumps(payload)],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        return f"Calculation failed: Missing data or invalid inputs. {result.stderr}"
        
    try:
        data = json.loads(result.stdout)
        return f"Range: {data['damage_range']}. Summary: {data['description']}"
    except Exception as e:
        return f"Failed to parse calc output: {e}"

def _run_calc(attacker_name: str, defender_name: str, move_name: str) -> str:
    """Fast, internal damage calculation without going through Langchain tools."""
    try:
        payload = {
            "gen": 9,
            "attacker": {"name": attacker_name, "details": {}},
            "defender": {"name": defender_name, "details": {}},
            "move": move_name
        }
        result = subprocess.run(
            ['node', 'calc_wrapper.js', json.dumps(payload)],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return f"Calc: {data['description']}"
    except Exception:
        pass
    return ""

class GeminiPokemonAgent:
    """Pokemon battle agent powered by Langchain and OpenRouter."""
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "poolside/laguna-xs-2.1:free"):
        """
        Initialize the Langchain Pokemon agent.
        
        Args:
            api_key: OpenRouter API key. If None, will try to get from environment
            model_name: OpenRouter model to use (starts with openrouter:)
        """
        # Get API key from parameter or environment
        self.api_key = api_key or os.getenv('OPENROUTER_API_KEY') or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            print("WARNING: No OPENROUTER_API_KEY found in environment. Agent calls may fail.")
            self.api_key = "dummy-key-to-allow-init"
        
        os.environ["OPENROUTER_API_KEY"] = self.api_key
        self.model_name = model_name
        
        # Load typechart for system prompt
        typechart_str = ""
        try:
            with open("typechart.json", "r") as f:
                typechart_str = f.read()
        except Exception:
            pass
            
        self.system_prompt = f"You are an expert Pokemon battle strategist. Use the provided state to make your choice.\nHere is the Type Chart for reference:\n{typechart_str}"
        
        # Load Gen 9 Random Battle Sets for opponent prediction
        self.random_sets = {}
        try:
            with open("pokemon-showdown/dist/data/random-battles/gen9/sets.json", "r") as f:
                self.random_sets = json.load(f)
        except Exception as e:
            print(f"Could not load random sets: {e}")
        self.opponent_knowledge = {'active_pokemon': '', 'team': {}}
        
        # Use ChatOpenRouter as requested
        try:
            self.llm = ChatOpenRouter(
                model=self.model_name,
                temperature=0,
            )
        except Exception as e:
            print(f"Failed to init ChatOpenRouter fallback: {e}")
    
    def create_battle_prompt(self, observation: dict, team_knowledge: Optional[dict] = None, compact_log: str = "", opponent_knowledge: Optional[dict] = None) -> str:
        """
        Create a detailed prompt for the Gemini model based on battle observation.
        
        Args:
            observation: Current battle state
            team_knowledge: Knowledge about our team composition
            
        Returns:
            Formatted prompt string
        """
        prompt_parts = []
        
        # System prompt
        prompt_parts.append("""""")
        
        # Add opponent knowledge if available
        if opponent_knowledge and opponent_knowledge.get('team'):
            prompt_parts.append("\n--- OPPONENT KNOWLEDGE ---")
            prompt_parts.append(f"Active Pokemon: {opponent_knowledge.get('active_pokemon', 'Unknown')}")
            for pkmn, details in opponent_knowledge['team'].items():
                moves = list(details.get('moves', []))
                move_str = ", ".join(moves) if moves else "Unknown"
                prompt_parts.append(f"  • {pkmn} - Moves: {move_str}, Item: {details.get('item', 'Unknown')}")
                
        # Add compact log if available
        if compact_log:
            prompt_parts.append("\n--- COMPACT TURN LOG ---")
            prompt_parts.append(compact_log)
        
        # Current turn and battle state
        prompt_parts.append(f"\n--- BATTLE STATE (Turn {observation.get('turn', '?')}) ---")
        
        # Our active Pokemon
        if observation.get('bench'):
            active_pokemon = None
            for pokemon in observation['bench']:
                if pokemon.get('active', False):
                    active_pokemon = pokemon
                    break
            
            if active_pokemon:
                hp_info = active_pokemon.get('hp_info', {})
                status = active_pokemon.get('status')
                prompt_parts.append(f"Our Active Pokemon: {active_pokemon['species']}")
                
                if hp_info.get('hp_percent'):
                    prompt_parts.append(f"HP: {hp_info['hp_percent']}%")
                elif hp_info.get('current_hp') and hp_info.get('max_hp'):
                    prompt_parts.append(f"HP: {hp_info['current_hp']}/{hp_info['max_hp']}")
                
                if status:
                    prompt_parts.append(f"Status: {status}")
                    
                if active_pokemon.get('ability'):
                    prompt_parts.append(f"Ability: {active_pokemon['ability']}")
        
        # Opponent's active Pokemon
        opponent = observation.get('opponent_active', {})
        if opponent.get('species'):
            prompt_parts.append(f"\nOpponent's Active: {opponent['species']}")
            if opponent.get('hp_percent') is not None:
                prompt_parts.append(f"Opponent HP: {opponent['hp_percent']}%")
            if opponent.get('status'):
                prompt_parts.append(f"Opponent Status: {opponent['status']}")
                
            # Attempt to get opponent's ability from knowledge
            if opponent_knowledge and opponent_knowledge.get('team') and opponent['species'] in opponent_knowledge['team']:
                opp_details = opponent_knowledge['team'][opponent['species']]
                if opp_details.get('ability'):
                    prompt_parts.append(f"Opponent Ability: {opp_details['ability']}")
                    
            # Inject possible moves from Random Battle sets
            sanitized_species = opponent['species'].lower().replace(" ", "").replace("-", "")
            if hasattr(self, 'random_sets') and sanitized_species in self.random_sets:
                possible_sets = self.random_sets[sanitized_species].get("sets", [])
                all_moves = set()
                all_abilities = set()
                for s in possible_sets:
                    for m in s.get("movepool", []):
                        all_moves.add(m)
                    for a in s.get("abilities", []):
                        all_abilities.add(a)
                if all_moves:
                    prompt_parts.append(f"Possible RandomBattle Moves: {', '.join(sorted(list(all_moves)))}")
                if all_abilities:
                    prompt_parts.append(f"Possible Abilities: {', '.join(sorted(list(all_abilities)))}")
        
        # Handle forced switch
        if observation.get('is_forced_switch', False):
            prompt_parts.append("\n⚠️ FORCED SWITCH REQUIRED ⚠️")
            switches = observation.get('available_switches', [])
            if switches:
                prompt_parts.append("Available Pokemon to switch to:")
                for switch in switches:
                    prompt_parts.append(f"  {switch['index']}. {switch['species']} ({switch['hp_status']})")
                prompt_parts.append("\nChoose the best Pokemon to switch to using 'action_type': 'switch' and the Pokemon's index number.")
            return '\n'.join(prompt_parts)
        
        
        # Available moves
        moves = observation.get('available_moves', [])
        if moves:
            prompt_parts.append("\nAvailable Moves:")
            
            # Check for choice lock (only one move available, others disabled)
            disabled_count = sum(1 for m in moves if m.get('disabled', False))
            if disabled_count == len(moves) - 1 and len(moves) > 1:
                prompt_parts.append("⚠️ YOU ARE CHOICE LOCKED ⚠️ - You can only use the one non-disabled move.")
                
            active_species = 'Unknown'
            if observation.get('bench'):
                for pokemon in observation['bench']:
                    if pokemon.get('active', False):
                        active_species = pokemon.get('species', 'Unknown')
                        break
            opponent_species = observation.get('opponent_active', {}).get('species', 'Unknown')
                
            for move in moves:
                move_name = move.get('move', move.get('id', 'Unknown'))
                pp_info = f"PP: {move.get('pp', '?')}/{move.get('maxpp', '?')}"
                target = move.get('target', '')
                disabled_str = " [DISABLED - DO NOT CHOOSE]" if move.get('disabled') else ""
                
                dmg_ctx = ""
                if not move.get('disabled') and opponent_species != 'Unknown' and active_species != 'Unknown':
                    calc_result = _run_calc(active_species, opponent_species, move_name)
                    if calc_result:
                        dmg_ctx = f" [{calc_result}]"
                        
                prompt_parts.append(f"  {move['index']}. {move_name} ({pp_info}) [Target: {target}]{dmg_ctx}{disabled_str}")
        
        # Available switches (for voluntary switching)
        switches = observation.get('available_switches', [])
        if switches:
            prompt_parts.append("\nBench Pokemon (can switch to):")
            for switch in switches:
                prompt_parts.append(f"  {switch['index']}. {switch['species']} ({switch['hp_status']})")
        
        # Recent battle events for context
        recent_events = observation.get('recent_events', [])
        if recent_events:
            prompt_parts.append("\nRecent Events:")
            for event in recent_events[-10:]:  # Last 5 events
                prompt_parts.append(f"  • {event}")
        
        #TODO: Field Conditions not being fetched appropriately, try to fetch from 
        weather = observation.get('weather')
        if weather:
            prompt_parts.append(f"\nWeather: {weather}")
        
        side_conditions = observation.get('side_conditions', {})
        if side_conditions:
            prompt_parts.append(f"Our Side Conditions: {list(side_conditions.keys())}")
        
        # Team knowledge - showing only available (alive) Pokemon
        if observation.get('available_switches'):
            prompt_parts.append(f"\nOur Available Pokemon:")
            
            for switch in observation['available_switches']:
                index = switch.get('index', '?')
                species = switch.get('species', 'Unknown')
                hp_status = switch.get('hp_status', 'Unknown HP')
                
                # Basic information
                prompt_parts.append(f"  {index}. {species} - HP: {hp_status}")
                
                # Add additional information from team_knowledge if available
                if team_knowledge and team_knowledge.get('pokemon'):
                    for pokemon in team_knowledge['pokemon']:
                        if pokemon.get('name') == species or pokemon.get('species') == species:
                            # Add moves if available
                            if pokemon.get('moves'):
                                moves_list = ', '.join(pokemon['moves'][:4])
                                prompt_parts.append(f"     Moves: {moves_list}")
                            
                            # Add ability if available
                            if pokemon.get('ability'):
                                prompt_parts.append(f"     Ability: {pokemon['ability']}")
                                
                            # Add item if available
                            if pokemon.get('item'):
                                prompt_parts.append(f"     Item: {pokemon['item']}")
                            
                            break
        
        # Strategic instructions
        prompt_parts.append("""
--- INSTRUCTIONS ---
Analyze the current battle state and the simulated scenarios provided below.
Choose the optimal move or switch to maximize your chances of winning.
If a move secures a KO, prioritize it unless it exposes you to an immediate counterattack.
If you are at a disadvantage, switch to a better defensive check.
""")
        
        return '\n'.join(prompt_parts)
        
    def predict_opponent_move(self, observation: dict, opponent_knowledge: Optional[dict] = None) -> str:
        """Use LLM to predict the opponent's single most likely move based on sets and state."""
        prompt = "Based on the current state, predict the SINGLE most likely move the opponent will use this turn.\n"
        
        opponent = observation.get('opponent_active', {})
        active = None
        if observation.get('bench'):
            for pk in observation['bench']:
                if pk.get('active'):
                    active = pk
                    break
        
        prompt += f"Our Active: {active.get('species', 'Unknown') if active else 'Unknown'}\n"
        prompt += f"Opponent Active: {opponent.get('species', 'Unknown')}\n"
        
        sanitized_species = opponent.get('species', '').lower().replace(" ", "").replace("-", "")
        if hasattr(self, 'random_sets') and sanitized_species in self.random_sets:
            possible_sets = self.random_sets[sanitized_species].get("sets", [])
            all_moves = set()
            for s in possible_sets:
                for m in s.get("movepool", []):
                    all_moves.add(m)
            if all_moves:
                prompt += f"Opponent Possible Moves: {', '.join(all_moves)}\n"
        
        prompt += "\nRespond with ONLY the EXACT NAME of the predicted move, nothing else."
        
        try:
            result = self.llm.invoke([("user", prompt)])
            content = getattr(result, "content", str(result))
            predicted_move = content.strip().split('\n')[0].strip(' "\'')
            return predicted_move
        except Exception as e:
            print(f"Failed to predict opponent move: {e}")
            return "Tackle" # Fallback
            
    def simulate_scenario(self, p1_name: str, p1_action: dict, p2_name: str, p2_action: dict, p1_hp: float, p2_hp: float) -> str:
        """Call simulate_turn.js to simulate the outcome of the turn."""
        payload = {
            "gen": 9,
            "p1": {
                "name": p1_name,
                "hp_percent": p1_hp,
                "action": p1_action
            },
            "p2": {
                "name": p2_name,
                "hp_percent": p2_hp,
                "action": p2_action
            }
        }
        
        try:
            result = subprocess.run(
                ['node', 'simulate_turn.js', json.dumps(payload)],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return f"{data['log']} (Result HP - Us: {data['p1_hp']}%, Them: {data['p2_hp']}%)"
        except Exception as e:
            pass
        return "Simulation failed."
    
    def get_battle_decision(self, observation: dict, team_knowledge: Optional[dict] = None, compact_log: str = "", opponent_knowledge: Optional[dict] = None) -> dict:
        """
        Get a battle decision from the Langchain Agent based on the current observation.
        
        Args:
            observation: Current battle state
            team_knowledge: Knowledge about our team
            
        Returns:
            Decision dictionary with action_type, choice, and reasoning
        """
        try:
            print("[DEBUG] create_battle_prompt...")
            # Create the base prompt
            prompt = self.create_battle_prompt(observation, team_knowledge, compact_log, opponent_knowledge)
            
            print("[DEBUG] PHASE 2 start...")
            # PHASE 2: Tree Search Sampling (1-Ply Simulator)
            # Skip simulation on forced switch since opponent doesn't move
            if not observation.get('is_forced_switch', False):
                print("[DEBUG] predict_opponent_move...")
                predicted_move = self.predict_opponent_move(observation, opponent_knowledge)
                print(f"[DEBUG] predict_opponent_move done: {predicted_move}")
                prompt += f"\n\n--- 1-PLY SIMULATIONS ---\nOpponent is predicted to use: {predicted_move}\n"
                
                # Get active names and HPs
                our_active = "Unknown"
                our_hp = 100
                if observation.get('bench'):
                    for pk in observation['bench']:
                        if pk.get('active'):
                            our_active = pk.get('species', 'Unknown')
                            hp_info = pk.get('hp_info', {})
                            our_hp = hp_info.get('hp_percent', 100)
                            break
                            
                opp_active = observation.get('opponent_active', {}).get('species', 'Unknown')
                opp_hp = observation.get('opponent_active', {}).get('hp_percent', 100)
                
                # Simulate our moves
                moves = observation.get('available_moves', [])
                for m in moves:
                    if not m.get('disabled', False):
                        move_name = m.get('move', m.get('id', 'Unknown'))
                        print(f"[DEBUG] simulating move: {move_name}")
                        sim_result = self.simulate_scenario(
                            our_active, {"type": "move", "name": move_name},
                            opp_active, {"type": "move", "name": predicted_move},
                            our_hp, opp_hp
                        )
                        prompt += f"\nIf we use {move_name}:\n{sim_result}"
                
                # Simulate our switches
                switches = observation.get('available_switches', [])
                for s in switches:
                    switch_name = s.get('species', 'Unknown')
                    # Parse switch HP (e.g., "85/100" or just assume 100)
                    switch_hp = 100
                    hp_status = s.get('hp_status', '')
                    if '/' in hp_status:
                        try:
                            parts = hp_status.replace('%', '').split('/')
                            switch_hp = (float(parts[0]) / float(parts[1])) * 100
                        except:
                            pass
                            
                    sim_result = self.simulate_scenario(
                        our_active, {"type": "switch", "name": switch_name, "hp_percent": switch_hp},
                        opp_active, {"type": "move", "name": predicted_move},
                        our_hp, opp_hp
                    )
                    prompt += f"\nIf we switch to {switch_name}:\n{sim_result}"
                
                prompt += "\n"
            
            system_instruction = """You are an expert Pokemon battle strategist. Analyze the current battle state and choose the best action.
            IMPORTANT: You must respond with ONLY a valid JSON object in this exact format:
            {
                "action_type": "move" or "switch",
                "choice": <number>,
                "reasoning": "<brief explanation>"
            }
            Where:
            - action_type: Either "move" to use a move or "switch" to switch Pokemon
            - choice: The index number of the move (1-4) or Pokemon slot (1-6) to use
            - reasoning: A brief strategic explanation (max 50 words)
            Do not include any other text or formatting. Only the JSON object."""
            
            print(f"[{'='*20} AGENT TEAM {'='*20}]")
            active = observation.get('active', 'Unknown')
            print(f"Active: {active}")
            print(f"Bench: {observation.get('bench', [])}")
            print(f"[{'='*20} OPPONENT KNOWLEDGE {'='*20}]")
            print(json.dumps(opponent_knowledge, indent=2, default=lambda o: list(o) if isinstance(o, set) else o) if opponent_knowledge else "None")
            print(f"{'='*60}")
            
            # Using direct LLM with JSON output
            try:
                messages = [
                    ("system", system_instruction),
                    ("user", prompt)
                ]
                print("[DEBUG] Invoking direct LLM...")
                result = self.llm.invoke(messages)
                print("[DEBUG] Direct LLM invoke done.")
                content = getattr(result, "content", str(result))
                if isinstance(content, list):
                    response_text = "".join(
                        block.get("text", "") if isinstance(block, dict) else str(block) 
                        for block in content
                    )
                else:
                    response_text = str(content)
            
            except Exception as e:
                print(f"Agent invoke failed: {e}")
                response_text = '{"action_type": "move", "choice": 1, "reasoning": "Fallback"}'
            
            print(f"[{'='*20} LLM RAW RESPONSE {'='*20}]\n{response_text}\n{'='*58}")
                
            # Parse the text response which should contain JSON from both methods
            thoughts = "Model Thought:\n" + response_text
            decision_dict = self.parse_llm_response(response_text, observation, thoughts)
            
            # Truncate prompt to ~1000 characters for the UI
            truncated_prompt = prompt[:1000] + "\n... [TRUNCATED]" if len(prompt) > 1000 else prompt
            decision_dict['input_prompt'] = truncated_prompt
            
            return decision_dict
                
        except Exception as e:
            print(f"OpenRouter API error: {e}")
            # Return fallback decision
            return self._get_fallback_decision(observation)
        
    def return_thoughts(self, response: Any) -> str:
        """
        Extract and return the model's thoughts from the response.
        """
        return str(response)

    def parse_llm_response(self, response_text: str, observation: dict, thoughts: str) -> dict:
        """
        Parse the LLM response into a structured decision.
        
        Args:
            response_text: Raw response from Gemini
            observation: Current battle state for validation
            
        Returns:
            Parsed decision dictionary
        """
        try:
            # Clean the response text
            response_text = response_text.strip()
            
            # Try to find JSON in the response
            if '{' in response_text and '}' in response_text:
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                json_text = response_text[start:end]
                
                # Parse JSON
                decision = json.loads(json_text)
                
                # Validate required fields
                if not all(key in decision for key in ['action_type', 'choice']):
                    raise ValueError("Missing required fields in response")
                
                # Validate action type
                if decision['action_type'] not in ['move', 'switch', 'wait']:
                    raise ValueError(f"Invalid action_type: {decision['action_type']}")
                
                # Validate choice based on available options
                if decision['action_type'] == 'move':
                    available_moves = observation.get('available_moves', [])
                    valid_indices = [m['index'] for m in available_moves]
                    if decision['choice'] not in valid_indices:
                        raise ValueError(f"Invalid move choice: {decision['choice']}")
                
                elif decision['action_type'] == 'switch':
                    available_switches = observation.get('available_switches', [])
                    valid_indices = [s['index'] for s in available_switches]
                    if decision['choice'] not in valid_indices:
                        raise ValueError(f"Invalid switch choice: {decision['choice']}")
                
                # Add default reasoning if missing
                if 'reasoning' not in decision:
                    decision['reasoning'] = f"Chose {decision['action_type']} {decision['choice']}"

                decision['thoughts'] = thoughts
                return decision
            
            else:
                raise ValueError("No JSON found in response")
                
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"Failed to parse LLM response: {e}")
            print(f"Raw response: {response_text}")
            return self._get_fallback_decision(observation)
    
    def _get_fallback_decision(self, observation: dict) -> dict:
        """
        Generate a fallback decision when LLM fails.
        
        Args:
            observation: Current battle state
            
        Returns:
            Safe fallback decision
        """
        # Handle forced switch
        if observation.get('is_forced_switch', False):
            switches = observation.get('available_switches', [])
            if switches:
                return {
                    'action_type': 'switch',
                    'choice': switches[0]['index'],
                    'reasoning': 'Fallback forced switch'
                }
        
        # Try to use a move
        moves = observation.get('available_moves', [])
        if moves:
            # Pick move with highest PP ratio
            best_move = moves[0]
            best_ratio = 0
            
            for move in moves:
                pp = move.get('pp', 0)
                max_pp = move.get('maxpp', 1)
                ratio = pp / max_pp if max_pp > 0 else 0
                
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_move = move
            
            return {
                'action_type': 'move',
                'choice': best_move['index'],
                'reasoning': 'Fallback move selection'
            }
        
        # Last resort - switch if possible
        switches = observation.get('available_switches', [])
        if switches:
            return {
                'action_type': 'switch',
                'choice': switches[0]['index'],
                'reasoning': 'Fallback switch'
            }
        
        # Ultimate fallback
        return {
            'action_type': 'move',
            'choice': 1,
            'reasoning': 'Ultimate fallback'
        }


# Global agent instance
_agent_instance = None

def init_gemini_agent(api_key: Optional[str] = None, model_name: str = "openai/gpt-5.4-mini") -> GeminiPokemonAgent:
    """
    Initialize the global agent instance. (Called gemini_agent for backward compatibility)
    
    Args:
        api_key: OpenRouter API key
        model_name: OpenRouter model to use (default: claude-3.5-sonnet)
        
    Returns:
        Initialized agent instance
    """
    global _agent_instance
    _agent_instance = GeminiPokemonAgent(api_key=api_key, model_name=model_name)
    return _agent_instance

def get_gemini_decision(observation: dict, team_knowledge: Optional[dict] = None, raw_log: str = "") -> dict:
    """
    Get a battle decision from the initialized Gemini agent.
    
    Args:
        observation: Current battle state
        team_knowledge: Knowledge about our team
        raw_log: The raw showdown log for the current turn to track opponent info
        
    Returns:
        Decision dictionary
    """
    global _agent_instance
    
    if _agent_instance is None:
        # Try to initialize with environment variable
        try:
            init_gemini_agent()
        except ValueError:
            raise ValueError(
                "Gemini agent not initialized. Call init_gemini_agent() first "
                "or set GOOGLE_AI_API_KEY environment variable"
            )

    compact_log = ""
    if raw_log:
        _agent_instance.opponent_knowledge, compact_log = update_tracker(raw_log, getattr(_agent_instance, 'opponent_knowledge', {'active_pokemon': '', 'team': {}}))

    return _agent_instance.get_battle_decision(observation, team_knowledge, compact_log, getattr(_agent_instance, 'opponent_knowledge', None))

def parse_llm_response(response_text: str, observation: dict) -> Tuple[str, int, str]:
    """
    Parse LLM response into action components for compatibility with existing code.
    
    Args:
        response_text: Raw LLM response
        observation: Current battle state
        
    Returns:
        Tuple of (action_type, choice, reasoning)
    """
    global _agent_instance
    
    if _agent_instance is None:
        # Create a temporary instance for parsing
        _agent_instance = GeminiPokemonAgent()
    
    decision = _agent_instance.parse_llm_response(response_text, observation)
    return decision['action_type'], decision['choice'], decision.get('reasoning', '')


# Example usage and testing
if __name__ == "__main__":
    # Example usage
    try:
        # Initialize agent (make sure to set GOOGLE_AI_API_KEY environment variable)
        agent = init_gemini_agent()
        
        # Example observation
        test_observation = {
            'turn': 3,
            'is_forced_switch': False,
            'available_moves': [
                {'index': 1, 'move': 'Fire Blast', 'pp': 5, 'maxpp': 8, 'target': 'normal'},
                {'index': 2, 'move': 'Solar Beam', 'pp': 10, 'maxpp': 10, 'target': 'normal'},
            ],
            'available_switches': [
                {'index': 2, 'species': 'Blastoise', 'hp_status': '100/100'},
                {'index': 3, 'species': 'Venusaur', 'hp_status': '85/100'},
            ],
            'opponent_active': {
                'species': 'Charizard',
                'hp_percent': 45,
                'status': None
            },
            'bench': [
                {
                    'index': 1,
                    'species': 'Charizard',
                    'active': True,
                    'hp_info': {'hp_percent': 75},
                    'status': None
                }
            ],
            'recent_events': [
                'P1 Charizard used Flamethrower',
                'P2 Blastoise took damage',
                'P2 switched to Charizard'
            ]
        }
        
        # Get decision
        decision = get_gemini_decision(test_observation)
        print("Decision:", decision)
        
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure to set GOOGLE_AI_API_KEY environment variable")