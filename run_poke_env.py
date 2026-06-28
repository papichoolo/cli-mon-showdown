import asyncio
import os
import sys
from poke_env_agent import GeminiPlayer
from poke_env import AccountConfiguration, ShowdownServerConfiguration

async def main():
    # You can set these in your terminal: export SHOWDOWN_USER="yourusername"
    username = os.getenv("SHOWDOWN_USER", "mikelarteta222")
    password = os.getenv("SHOWDOWN_PASS", "poopooman")
    
    print("Initializing Poke-env...")
    # Set up account configs
    account_config = AccountConfiguration(username, password)
    
    # Initialize our new LLM player
    # Uses gen9randombattle by default. You can change it to gen9ou, etc.
    player = GeminiPlayer(
        account_configuration=account_config,
        server_configuration=ShowdownServerConfiguration,
        battle_format="gen9randombattle",
    )
    
    print(f"Logged in as {player.username}. Searching for a battle on the ladder...")
    
    # Play 1 game on the ladder
    try:
        await player.ladder(1)
        print("Battle complete! Check your Showdown history.")
    except Exception as e:
        print(f"Error during battle: {e}")

if __name__ == "__main__":
    # Ensure poke-env is installed
    try:
        import poke_env
    except ImportError:
        print("Error: poke-env is not installed. Please run:")
        print("source .venv/bin/activate && pip install poke-env")
        sys.exit(1)
        
    asyncio.run(main())
