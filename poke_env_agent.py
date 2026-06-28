import os
import json
import asyncio
import subprocess
from dotenv import load_dotenv

from typing import Optional
from poke_env.player import Player

from langchain_openrouter import ChatOpenRouter
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()


def _run_calc(attacker_name: str, defender_name: str, move_name: str) -> str:
    try:
        payload = {
            "gen": 9,
            "attacker": {"name": attacker_name, "details": {}},
            "defender": {"name": defender_name, "details": {}},
            "move": move_name,
        }
        result = subprocess.run(
            ["node", "calc_wrapper.js", json.dumps(payload)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return f"Calc: {data['description']}"
    except Exception:
        pass
    return ""


class GeminiPlayer(Player):
    def __init__(
        self, api_key: str = None, model_name: str = "openai/gpt-5.4-mini", **kwargs
    ):
        super().__init__(**kwargs)
        self.api_key = (
            api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        )

        # ChatOpenRouter STRICTLY requires the OPENROUTER_API_KEY environment variable to be set,
        # even if you loaded your key from a variable named OPENAI_API_KEY.
        if self.api_key:
            os.environ["OPENROUTER_API_KEY"] = self.api_key
        else:
            os.environ["OPENROUTER_API_KEY"] = "dummy-key"

        self.llm = ChatOpenRouter(
            model_name=model_name,
            temperature=0,
            model_kwargs={"response_format": {"type": "json_object"}},
        )

        typechart_str = ""
        try:
            with open("typechart.json", "r") as f:
                typechart_str = f.read()
        except Exception:
            pass

        self.system_prompt = f"""You are an expert Pokemon battle strategist.
--- INSTRUCTIONS ---
Analyze the current battle state, focusing on the expected damage calculations provided.
Choose the optimal move or switch to maximize your chances of winning.
If a move secures a KO, prioritize it unless it exposes you to an immediate counterattack.
If you are at a disadvantage, switch to a better defensive check.

Respond ONLY with a valid JSON object matching this schema:
{{
  "action_type": "move" or "switch",
  "choice": "<name of the move or pokemon to switch to>",
  "reasoning": "<short reasoning>"
}}

Here is the Type Chart for reference:
{typechart_str}"""

    def choose_move(self, battle):
        prompt_parts = []
        prompt_parts.append(f"Turn: {battle.turn}")

        # Weather / Field
        if battle.weather:
            prompt_parts.append(f"Weather: {list(battle.weather.keys())[0].name}")
        if battle.fields:
            fields = [f.name for f in battle.fields]
            prompt_parts.append(f"Field: {', '.join(fields)}")

        # Side conditions
        if battle.side_conditions:
            conditions = [c.name for c in battle.side_conditions]
            prompt_parts.append(f"Our Side Conditions: {', '.join(conditions)}")
        if battle.opponent_side_conditions:
            conditions = [c.name for c in battle.opponent_side_conditions]
            prompt_parts.append(f"Opponent Side Conditions: {', '.join(conditions)}")

        # Our active
        active = battle.active_pokemon
        if active:
            prompt_parts.append(f"\nOur Active Pokemon: {active.species}")
            types = [t.name for t in active.types if t]
            prompt_parts.append(f"Types: {'/'.join(types)}")
            prompt_parts.append(f"HP: {active.current_hp_fraction * 100:.1f}%")
            if active.status:
                prompt_parts.append(f"Status: {active.status.name}")
            if active.ability:
                prompt_parts.append(f"Ability: {active.ability}")
            if active.item:
                prompt_parts.append(f"Item: {active.item}")
            if active.boosts:
                boosts_str = ", ".join(f"{k}: {v}" for k, v in active.boosts.items())
                prompt_parts.append(f"Boosts: {boosts_str}")

        # Opponent active
        opp = battle.opponent_active_pokemon
        if opp:
            prompt_parts.append(f"\nOpponent's Active: {opp.species}")
            types = [t.name for t in opp.types if t]
            prompt_parts.append(f"Types: {'/'.join(types)}")
            prompt_parts.append(f"HP: {opp.current_hp_fraction * 100:.1f}%")
            if opp.status:
                prompt_parts.append(f"Status: {opp.status.name}")
            if opp.ability:
                prompt_parts.append(f"Ability: {opp.ability}")
            if opp.item:
                prompt_parts.append(f"Item: {opp.item}")
            if opp.boosts:
                boosts_str = ", ".join(f"{k}: {v}" for k, v in opp.boosts.items())
                prompt_parts.append(f"Boosts: {boosts_str}")

        # Opponent Team (Revealed)
        revealed_team = [p for p in battle.opponent_team.values() if not p.active]
        if revealed_team:
            prompt_parts.append("\nOpponent's Revealed Bench:")
            for p in revealed_team:
                moves = [m for m in p.moves]
                moves_str = ", ".join(moves) if moves else "Unknown"
                prompt_parts.append(
                    f" - {p.species} (HP: {p.current_hp_fraction * 100:.1f}%) | Moves: {moves_str}"
                )

        # Forced Switch check
        if battle.force_switch:
            prompt_parts.append("\n⚠️ FORCED SWITCH REQUIRED ⚠️")
            prompt_parts.append(
                "Your active Pokemon fainted or is forced out. You must choose a switch."
            )

        # Available moves
        if battle.available_moves:
            prompt_parts.append("\nAvailable Moves:")
            if (
                len(battle.available_moves) == 1
                and active
                and active.item
                and "choice" in active.item.lower()
            ):
                prompt_parts.append("⚠️ YOU ARE CHOICE LOCKED ⚠️")

            for move in battle.available_moves:
                dmg_ctx = ""
                if active and opp:
                    calc_result = _run_calc(active.species, opp.species, move.id)
                    if calc_result:
                        dmg_ctx = f" [{calc_result}]"
                prompt_parts.append(
                    f" - {move.id} (Power: {move.base_power}, Type: {move.type.name}){dmg_ctx}"
                )

        # Available switches
        if battle.available_switches:
            prompt_parts.append("\nAvailable Switches:")
            for switch in battle.available_switches:
                types = [t.name for t in switch.types if t]
                types_str = "/".join(types)
                prompt_parts.append(
                    f" - {switch.species} (Types: {types_str}, HP: {switch.current_hp_fraction * 100:.1f}%, Status: {switch.status.name if switch.status else 'None'})"
                )

        prompt = "\n".join(prompt_parts)

        try:
            print(f"\n[{'=' * 20} LLM Request for Turn {battle.turn} {'=' * 20}]")
            print(prompt)
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=prompt),
            ]
            response = self.llm.invoke(messages)

            # Parse JSON
            content = response.content.replace("```json", "").replace("```", "")
            decision = json.loads(content)
            print(f"\nLLM Decision: {decision}")

            action_type = decision.get("action_type")
            choice_name = (
                decision.get("choice", "").lower().replace(" ", "").replace("-", "")
            )

            if action_type == "move":
                for move in battle.available_moves:
                    if move.id.lower().replace(" ", "").replace("-", "") == choice_name:
                        # Dump to JSON file for the Web Dashboard visualization
                        try:
                            state_dump = {
                                "turn": battle.turn,
                                "reasoning": decision.get("reasoning", "No reasoning provided"),
                                "action_type": decision.get("action_type", ""),
                                "choice": decision.get("choice", ""),
                                "prompt": prompt
                            }
                            with open("agent_state.json", "w", encoding="utf-8") as f:
                                json.dump(state_dump, f)
                        except Exception as e:
                            print(f"Failed to write agent_state.json: {e}")
                        return self.create_order(move)
            elif action_type == "switch":
                for switch in battle.available_switches:
                    if (
                        switch.species.lower().replace(" ", "").replace("-", "")
                        == choice_name
                    ):
                        # Dump to JSON file for the Web Dashboard visualization
                        try:
                            state_dump = {
                                "turn": battle.turn,
                                "reasoning": decision.get("reasoning", "No reasoning provided"),
                                "action_type": decision.get("action_type", ""),
                                "choice": decision.get("choice", ""),
                                "prompt": prompt
                            }
                            with open("agent_state.json", "w", encoding="utf-8") as f:
                                json.dump(state_dump, f)
                        except Exception as e:
                            print(f"Failed to write agent_state.json: {e}")
                        return self.create_order(switch)

        except Exception as e:
            print(f"LLM Error: {e}")

        # Fallback to random/first available if LLM fails or makes invalid choice
        print("Falling back to random choice due to invalid LLM output or error.")
        return self.choose_random_move(battle)
