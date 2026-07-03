import { calculate, Generations, Pokemon, Move, Field } from '@smogon/calc';

const args = JSON.parse(process.argv[2]);
const gen = Generations.get(args.gen || 9);

const field = args.field ? new Field(args.field) : new Field();

let p1Action = args.p1.action;
let p2Action = args.p2.action;

let p1Poke = new Pokemon(gen, args.p1.name, args.p1.details || {});
let p2Poke = new Pokemon(gen, args.p2.name, args.p2.details || {});

let p1Hp = args.p1.hp_percent || 100;
let p2Hp = args.p2.hp_percent || 100;

// Resolve priority
let p1Priority = p1Action.type === 'switch' ? 6 : (new Move(gen, p1Action.name)).priority;
let p2Priority = p2Action.type === 'switch' ? 6 : (new Move(gen, p2Action.name)).priority;

let p1First = false;
if (p1Priority > p2Priority) {
    p1First = true;
} else if (p2Priority > p1Priority) {
    p1First = false;
} else {
    if (p1Poke.stats.spe > p2Poke.stats.spe) {
        p1First = true;
    } else if (p2Poke.stats.spe > p1Poke.stats.spe) {
        p1First = false;
    } else {
        p1First = true; // Tie breaker
    }
}

let log = [];

function doAction(isP1) {
    let action = isP1 ? p1Action : p2Action;
    let attacker = isP1 ? p1Poke : p2Poke;
    let defender = isP1 ? p2Poke : p1Poke;
    
    // Check if fainted
    if (isP1 && p1Hp <= 0) return;
    if (!isP1 && p2Hp <= 0) return;

    if (action.type === 'switch') {
        if (isP1) {
            p1Poke = new Pokemon(gen, action.name, action.details || {});
            p1Hp = action.hp_percent || 100;
        } else {
            p2Poke = new Pokemon(gen, action.name, action.details || {});
            p2Hp = action.hp_percent || 100;
        }
        log.push(`${isP1 ? 'We' : 'Opponent'} switched to ${action.name}.`);
        return;
    }

    if (action.type === 'move') {
        let move = new Move(gen, action.name);
        let result = calculate(gen, attacker, defender, move, field);
        let dmgRange = result.damage;
        let avgDmg = 0;
        
        // dmgRange can be an array of numbers, or a single number (0)
        if (Array.isArray(dmgRange)) {
            avgDmg = dmgRange[Math.floor(dmgRange.length / 2)]; // Take median roll
        } else {
            avgDmg = dmgRange;
        }

        // Convert damage to percent of defender max HP
        // smogon calc returns raw damage numbers. We divide by defender max HP.
        let maxHp = defender.maxHP();
        if (!maxHp || maxHp === 0) maxHp = 100; // fallback
        
        let percentDmg = (avgDmg / maxHp) * 100;
        if (percentDmg > 100) percentDmg = 100;

        if (isP1) {
            p2Hp -= percentDmg;
            if (p2Hp < 0) p2Hp = 0;
            log.push(`We used ${move.name} dealing ~${percentDmg.toFixed(1)}% to ${defender.name}.`);
        } else {
            p1Hp -= percentDmg;
            if (p1Hp < 0) p1Hp = 0;
            log.push(`Opponent used ${move.name} dealing ~${percentDmg.toFixed(1)}% to ${defender.name}.`);
        }
        
        if (p1Hp <= 0 && !isP1) log.push(`We fainted!`);
        if (p2Hp <= 0 && isP1) log.push(`Opponent fainted!`);
    }
}

if (p1First) {
    doAction(true);
    doAction(false);
} else {
    doAction(false);
    doAction(true);
}

console.log(JSON.stringify({
    log: log.join(' '),
    p1_hp: Math.max(0, p1Hp).toFixed(1),
    p2_hp: Math.max(0, p2Hp).toFixed(1)
}));
