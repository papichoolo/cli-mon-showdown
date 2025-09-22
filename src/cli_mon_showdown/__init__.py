"""CLI wrapper for Pokemon Showdown simulations."""

import os
from pathlib import Path

from .cli import main
from .showdown_wrapper import ShowdownWrapper, generate_random_team

__all__ = ["main", "ShowdownWrapper", "generate_random_team", "get_pokemon_showdown_path"]

def get_pokemon_showdown_path():
    """Find the Pokemon Showdown installation path."""
    # Try different locations where Pokemon Showdown might be
    current_dir = Path.cwd()
    package_dir = Path(__file__).parent
    
    # Possible paths to check (in order of preference)
    possible_paths = [
        current_dir / "pokemon-showdown",  # Development environment
        package_dir / "pokemon-showdown",  # Package installation (new location)
        package_dir / ".." / "pokemon-showdown",  # Package installation (old location)
        current_dir / "src" / "pokemon-showdown",  # Alternative layout
        package_dir / ".." / ".." / "pokemon-showdown",  # Another alternative
    ]
    
    for path in possible_paths:
        if path.exists() and (path / "pokemon-showdown").exists():
            return str(path)
    
    # Fallback to default relative path
    return "pokemon-showdown"
