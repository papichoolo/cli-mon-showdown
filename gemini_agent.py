"""
Gemini API Agent for Pokemon Showdown Battle Decisions

This module provides an interface to Google's Gemini API for making strategic
Pokemon battle decisions based on game state observations.
"""

#import chunk
import json
import os
from typing import Dict, Optional, Tuple, Any
from google import genai
from pydantic import BaseModel, Field
#from google.generativeai.types import HarmCategory, HarmBlockThreshold
from google.genai import types

class ModelAction(BaseModel):
    action_type: str = Field(..., description="Either 'move' or 'switch'")
    choice: int = Field(..., description="Index of the move (1-4) or Pokemon slot (1-6)")
    reasoning: Optional[str] = Field(None, description="Brief explanation of the choice")


class GeminiPokemonAgent:
    """Pokemon battle agent powered by Google's Gemini API."""
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        """
        Initialize the Gemini Pokemon agent.
        
        Args:
            api_key: Google AI API key. If None, will try to get from environment
            model_name: Gemini model to use
        """
        # Get API key from parameter or environment
        self.api_key = api_key or os.getenv('GOOGLE_AI_API_KEY') or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError(
                "No API key provided. Set GOOGLE_AI_API_KEY environment variable "
                "or pass api_key parameter to GeminiPokemonAgent()"
            )
        
        # # Configure Gemini
        # genai.configure(api_key=self.api_key)
        # self.model_name = model_name
        
        # # Initialize the model with safety settings
        # self.model = genai.GenerativeModel(
        #     model_name=model_name,
        #     safety_settings={
        #         HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        #         HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        #         HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        #         HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        #     }
        # )
        
        # # Generation config for consistent responses
        # self.generation_config = genai.types.GenerationConfig(
        #     temperature=0.7,
        #     top_p=0.8,
        #     top_k=40,
        #     max_output_tokens=500,
        # )
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name


    
    def create_battle_prompt(self, observation: dict, team_knowledge: Optional[dict] = None) -> str:
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
        
        # Opponent's active Pokemon
        opponent = observation.get('opponent_active', {})
        if opponent.get('species'):
            prompt_parts.append(f"\nOpponent's Active: {opponent['species']}")
            if opponent.get('hp_percent') is not None:
                prompt_parts.append(f"Opponent HP: {opponent['hp_percent']}%")
            if opponent.get('status'):
                prompt_parts.append(f"Opponent Status: {opponent['status']}")
        
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
            for move in moves:
                move_name = move.get('move', move.get('id', 'Unknown'))
                pp_info = f"PP: {move.get('pp', '?')}/{move.get('maxpp', '?')}"
                target = move.get('target', '')
                prompt_parts.append(f"  {move['index']}. {move_name} ({pp_info}) [Target: {target}]")
        
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
"turn_budgeting": {
"early_game": "scout sets, establish hazards/positioning",
"mid_game": "chip key checks, force trades, deny removal",
"end_game": "enable cleaner/wincon, preserve necessary sacks"
}
},
"core_principles": [
"Identify win conditions on preview and after each reveal",
"Play to highest EV of the game state; avoid low-reward overpredictions early",
"Preserve team roles: wall, pivot, breaker, cleaner, hazard control",
"Trade HP for progress only when it advances a wincon or removes a hard check",
"Track information relentlessly; update lines when new info appears"
],
"priority_order": [
"Prevent immediate KOs and checkmates",
"Secure KOs or decisive chip on opposing wincon",
"Deny hazard removal or set hazards when uncontested",
"Capitalize on free turns with setup, pivot, or double switch",
"Conserve key resources (HP, PP, Tera, items) for endgame"
],
"attacking_rules": [
"Use the strongest reliable move that secures a KO or 2HKO without overexposing",
"Respect resist/immunity abilities (Flash Fire, Storm Drain, Volt Absorb, Sap Sipper)",
"Prefer guaranteed damage over reads when ahead; predict when behind or at parity with clear payoff",
"Avoid contact into Rocky Helmet/Rough Skin/Iron Barbs when chip would flip ranges",
"Exploit chip thresholds: Stealth Rock + Spikes + Leftovers denial to push into KO range"
],
"switching_rules": [
"Switch when current mon cannot 2HKO and is 2HKO’d back or risks crippling status",
"Use pivots (U-turn/Volt Switch/Flip Turn/Teleport) to seize momentum into breakers",
"Double switch to catch obvious answers once they’re constrained",
"Preserve defensive glue vs opposing breakers; do not sack your only check"
],
"type_matchups": [
"Always prefer STAB super-effective over neutral unless accuracy/priority/coverage dictates",
"Do not Tera into a type that opens new 4x weaknesses unless it immediately flips the game",
"Punish locked Choice users by switching into resists/immunities and gaining tempo"
],
"pp_management": [
"Stall low-PP threats (Hydro Steam, Make It Rain, Overheat, Moonblast on key walls) when safe",
"Avoid spamming low-PP nukes unless it converts into board control or a KO",
"Use Recover/Slack Off/Strength Sap intelligently; never heal into a free setup"
],
"hazards": [
"Set Stealth Rock early if safe; add Spikes/Tspikes when removal is pressured or blocked",
"Spin/Defog only when hazard state meaningfully alters ranges or protects wincon",
"Block removal with Ghost into Spin, pressure Defoggers with breakers/status",
"Leverage Heavy-Duty Boots knowledge; punish non-Boots pivots with chip cycles"
],
"status_and_items": [
"Spread status to disable walls/cleaners; prioritize Toxic on bulky pivots, Para on fast threats, Burn on physicals",
"Do not status Guts/Toxic Boost/Poison Heal or Synchronize without payoff",
"Scout items via damage rolls, recovery (Leftovers/Black Sludge), and speed ties (Choice Scarf inference)",
"Knock Off high-value targets early; preserve your Boots on hazard-weak mons"
],
"weather_terrain_screens": [
"Count turns for weather/terrain/screens; plan sacks and pivots to waste turns",
"Deny setters when possible; pressure abusers during downtime",
"Against screens HO, prioritize chip + phazing/taunt; keep hazards up"
],
"setup_and_priority": [
"Set up only on forced switches or neutered targets; ensure answers are removed or crippled",
"Use priority to revenge kill or force Tera; avoid revealing priority unnecessarily if the surprise secures endgame",
"Phaze or Encore opposing setup if checks are strained"
],
"terastalization": [
"Do not Tera without a concrete tactical or strategic gain (KO, walling a threat, enabling sweep)",
"Track opposing likely Tera types from team structure; respect defensive Tera to block KOs",
"Save Tera for the mon most aligned with your wincon unless an emergency defense is required"
],
"prediction_policy": [
"Default to safe lines until enough info is gathered; minimize coin flips early",
"Take calculated reads when payoff is high and downside is limited by sacks or hazards",
"Use prior reveals and common sets to weight options; update as calcs contradict expectations"
],
"risk_management": [
"Avoid status into Natural Cure/Rest or Flame Body unless payoff > risk",
"Respect lure coverage (e.g., Fire Blast Garchomp, Ice Beam Slowking-Galar) after telltale sequences",
"Account for crit risk when behind a sub or versus boosted foes; choose lines that keep outs"
],
"information_tracking": {
"track": [
"HP percentages and exact damage rolls",
"Revealed moves, items, abilities, Tera types",
"Speed tiers from in-battle order and tie outcomes",
"Hazard state and removal resources",
"Field turn counters (weather/terrain/screens/room)"
],
"update_frequency": "after every action; recalc KO ranges post-chip"
},
"endgame": [
"Identify cleaner candidates (Scarfers, Dragon Dancers, Booster Energy, priority users)",
"Preserve sacks to generate safe entries for cleaner",
"Force 50/50s only when winning both branches or when losing otherwise"
],
"edge_cases": [
"Versus Trick/Encore: do not give free locks; pivot to low-opportunity-cost mons",
"Versus Substitute: break sub first unless you can phaze or outpace",
"Versus Unaware: prioritize raw power, hazards, and status over boosting",
"Versus Stall: stack hazards, deny recovery with Taunt/Knock, and manage PP",
"Versus HO: trade aggressively, keep hazards, deny setup with priority/Encore/phazing"
],
"execution_rules": [
"Always output a legal move or switch; include a brief reason if required by interface",
"If no safe option exists, choose the line that maximizes outs and preserves wincon odds",
"On timers, prefer deterministic safe lines over deep calcs"
],
"original_guidelines_integrated": [
"If opponent is low HP, prioritize attacking moves",
"If our Pokemon is low HP or has bad status, consider switching",
"Use type advantages when possible",
"Conserve PP on powerful moves",
"Consider weather and field effects",
"Switch to counter opponent's type if needed"
]
}""")
        
        return '\n'.join(prompt_parts)
    
    def get_battle_decision(self, observation: dict, team_knowledge: Optional[dict] = None) -> dict:
        """
        Get a battle decision from Gemini based on the current observation.
        
        Args:
            observation: Current battle state
            team_knowledge: Knowledge about our team
            
        Returns:
            Decision dictionary with action_type, choice, and reasoning
        """
        try:
            # Create the prompt
            prompt = self.create_battle_prompt(observation, team_knowledge)
            #print(prompt)
            # Generate response from Gemini
            response = self.client.models.generate_content(
                model=self.model_name,
                config=types.GenerateContentConfig(
                    system_instruction="""You are an expert Pokemon battle strategist. Analyze the current battle state and choose the best action.
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
                    Do not include any other text or formatting. Only the JSON object.""",
    
                    temperature=0.7,
response_mime_type="application/json",
response_schema=ModelAction,
thinking_config=types.ThinkingConfig(
thinking_budget=-1,
include_thoughts=True)
            ),
            contents=prompt
            )
            #print(prompt)
            # Parse the response
            thoughts = self.return_thoughts(response)
            #print("Thoughts:", thoughts)
            if response.text:
                return self.parse_llm_response(response.text, observation, thoughts)
            else:
                raise ValueError("Empty response from Gemini")
                
        except Exception as e:
            print(f"Gemini API error: {e}")
            # Return fallback decision
            return self._get_fallback_decision(observation)
        
    def return_thoughts(self, response: Any) -> str:
        """
        Extract and return the model's thoughts from the response.
        
        Args:
            response: Full response object from Gemini"""
        thoughts = ""
        for part in response.candidates[0].content.parts:
            if part.thought:
                thoughts += f"Model Thought:\n{part.text}\n"
        return thoughts

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

def init_gemini_agent(api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash-lite") -> GeminiPokemonAgent:
    """
    Initialize the global Gemini agent instance.
    
    Args:
        api_key: Google AI API key
        model_name: Gemini model to use
        
    Returns:
        Initialized agent instance
    """
    global _agent_instance
    _agent_instance = GeminiPokemonAgent(api_key=api_key, model_name=model_name)
    return _agent_instance

def get_gemini_decision(observation: dict, team_knowledge: Optional[dict] = None) -> dict:
    """
    Get a battle decision from the initialized Gemini agent.
    
    Args:
        observation: Current battle state
        team_knowledge: Knowledge about our team
        
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

    return _agent_instance.get_battle_decision(observation, team_knowledge)

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