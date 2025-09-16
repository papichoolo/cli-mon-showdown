"""
Gemini API Agent for Pokemon Showdown Battle Decisions

This module provides an interface to Google's Gemini API for making strategic
Pokemon battle decisions based on game state observations.
"""

import json
import os
from typing import Dict, Optional, Tuple, Any
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold


class GeminiPokemonAgent:
    """Pokemon battle agent powered by Google's Gemini API."""
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-1.5-flash"):
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
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model_name = model_name
        
        # Initialize the model with safety settings
        self.model = genai.GenerativeModel(
            model_name=model_name,
            safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
        
        # Generation config for consistent responses
        self.generation_config = genai.types.GenerationConfig(
            temperature=0.7,
            top_p=0.8,
            top_k=40,
            max_output_tokens=500,
        )
    
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
        prompt_parts.append("""You are an expert Pokemon battle strategist. Analyze the current battle state and choose the best action.

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

Do not include any other text or formatting. Only the JSON object.""")
        
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
            for event in recent_events[-5:]:  # Last 5 events
                prompt_parts.append(f"  • {event}")
        
        # Field conditions
        weather = observation.get('weather')
        if weather:
            prompt_parts.append(f"\nWeather: {weather}")
        
        side_conditions = observation.get('side_conditions', {})
        if side_conditions:
            prompt_parts.append(f"Our Side Conditions: {list(side_conditions.keys())}")
        
        # Team knowledge if available
        if team_knowledge and team_knowledge.get('pokemon'):
            prompt_parts.append(f"\nOur Team Composition:")
            for i, pokemon in enumerate(team_knowledge['pokemon'][:6], 1):
                moves_list = ', '.join(pokemon.get('moves', [])[:4])
                prompt_parts.append(f"  {i}. {pokemon['name']} - {moves_list}")
        
        # Strategic instructions
        prompt_parts.append("""
--- STRATEGIC GUIDELINES ---
1. If opponent is low HP, prioritize attacking moves
2. If our Pokemon is low HP or has bad status, consider switching
3. Use type advantages when possible
4. Conserve PP on powerful moves
5. Consider weather and field effects
6. Switch to counter opponent's type if needed

Remember: Respond with ONLY the JSON object, no other text!""")
        
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
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config
            )
            
            # Parse the response
            if response.text:
                return self.parse_llm_response(response.text, observation)
            else:
                raise ValueError("Empty response from Gemini")
                
        except Exception as e:
            print(f"Gemini API error: {e}")
            # Return fallback decision
            return self._get_fallback_decision(observation)
    
    def parse_llm_response(self, response_text: str, observation: dict) -> dict:
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

def init_gemini_agent(api_key: Optional[str] = None, model_name: str = "gemini-1.5-flash") -> GeminiPokemonAgent:
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