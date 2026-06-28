// calc_wrapper.js
import { calculate, Generations, Pokemon, Move, Field } from '@smogon/calc';

const args = JSON.parse(process.argv[2]);
const gen = Generations.get(args.gen);

const attacker = new Pokemon(gen, args.attacker.name, args.attacker.details);
const defender = new Pokemon(gen, args.defender.name, args.defender.details);
const move = new Move(gen, args.move);
const field = args.field ? new Field(args.field) : new Field();

const result = calculate(gen, attacker, defender, move, field);

console.log(JSON.stringify({
    damage_range: result.damage,
    description: result.desc()
}));
