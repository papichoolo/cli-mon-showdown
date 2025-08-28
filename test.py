import os
import re
import json
import google.generativeai as genai  # Corrected import
from dotenv import load_dotenv

load_dotenv(override=True)

# Configure Gemini client
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def extract_json_from_code_block(text):
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()

def return_moveset(info,basestats):
    prompt = (
        f"You are an expert in the Smogon competitive Pokémon metagame. "
        f"Given the Pokémon {info}, and base stats: {basestats}, "
        "generate the most viable competitive moveset that is actually used in high-level play. "
        "Only respond with a JSON object in the format: "
        "{\"moves\": [\"Move1\", \"Move2\", \"Move3\", \"Move4\"]}"
    )

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)

    raw_output = response.text
    print("Raw output:", raw_output)  # Debug

    json_str = extract_json_from_code_block(raw_output)
    try:
        moveset = json.loads(json_str)
        return moveset["moves"]
    except json.JSONDecodeError as e:  # More specific exception handling
        print(f"Error decoding JSON from output: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

def main():
    info = "Gholdengo"
    basestats = {"hp": 87, "attack": 60, "defense": 95, "sp_attack": 133, "sp_defense": 91, "speed": 84}

    moveset = return_moveset(info, basestats)

    if moveset:
        print(f"Most Viable Moveset for {info}:")
        print(json.dumps(moveset, indent=2))
    else:
        print(f"Could not generate a viable moveset for {info}.")

if __name__ == "__main__":
    main()