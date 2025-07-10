from openai import AsyncAzureOpenAI
from dotenv import load_dotenv
import os
import re
import json
import asyncio
from agents import set_default_openai_client, Agent, Runner
load_dotenv(override=True)
client = AsyncAzureOpenAI(
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
)
set_default_openai_client(client)

agent1=Agent(
    model="gpt-4o",
    name="Pokemon Identifier",
    instructions="You are an important tool for identifying the Pokemon in a Competitive Pokemon Battle. Given the Pokemon, create a competitve Description in the Smogon Metagame this is most useful in. Only Respond the metagame, its Pros, Checks and Counters.",
)



moveset_agent=Agent(
    model="gpt-4o",
    name="Moveset Maker",
    instructions="You are an important tool for creating competitive movesets for Pokemon in the Smogon Metagame. Given the Pokemon, create a competitive moveset including moves.",
)
def extract_json_from_code_block(text):
    # Match code block, optionally starting with ```json or ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()

def return_moveset(info, basestats):
    prompt = (
        f"Here is the Movepool for the Pokemon: {info}, and here are the Base Stats: {basestats}. "
        "Create a competitive moveset for this Pokemon in the Smogon Metagame. "
        "Only respond with a JSON object in the format: "
        "{\"moves\": [\"Move1\", \"Move2\", \"Move3\", \"Move4\"]}"
    )
    
    # Run the agent and get the raw output
    result = Runner.run_sync(moveset_agent, prompt)
    raw_output = result.final_output
    print("Raw output:", raw_output)  # For debugging

    # Extract JSON from code block if present
    json_str = extract_json_from_code_block(raw_output)
    try:
        moveset = json.loads(json_str)
        return moveset["moves"]
    except Exception as e:
        print(f"Error decoding JSON from output: {e}")
        return None


def main():
    # Example data for Gholdengo
    gholdengo_moves = "Make It Rain, Shadow Ball, Focus Blast, Nasty Plot, Trick, Thunderbolt, Psyshock"
    gholdengo_stats = {"hp": 87, "attack": 60, "defense": 95, "sp_attack": 133, "sp_defense": 91, "speed": 84}
    
    # Get the moveset
    moves = return_moveset(gholdengo_moves, gholdengo_stats)
    
    # Print the result
    if moves:
        print("Competitive Moveset for Gholdengo:")
        for move in moves:
            print(f"- {move}")

if __name__ == "__main__":
    main()
