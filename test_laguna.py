import os
from dotenv import load_dotenv
load_dotenv()
from gemini_agent import init_gemini_agent, get_gemini_decision
import time

agent = init_gemini_agent()

test_observation = {
    'turn': 3,
    'is_forced_switch': False,
    'available_moves': [
        {'index': 1, 'move': 'Fire Blast', 'pp': 5, 'maxpp': 8, 'target': 'normal'},
    ],
    'available_switches': [],
    'opponent_active': {
        'species': 'Charizard',
        'hp_percent': 45,
        'status': None
    },
    'bench': [],
    'recent_events': []
}

print("Starting get_gemini_decision...")
start = time.time()
decision = get_gemini_decision(test_observation)
end = time.time()
print(f"Decision in {end - start:.2f} seconds:", decision)
