// teamutils.js
import {Dex} from '@pkmn/sim';
import {Teams as SetsTeams} from '@pkmn/sets';
import fs from 'fs';

const file = process.argv[2];
if (!file) {
  console.error("Usage: node teamutils.js <team-file>");
  process.exit(1);
}

const text = fs.readFileSync(file, 'utf8');

// Parse the Showdown importable text into structured data
// Use @pkmn/sets to parse importable text into a Team object
const teamObj = SetsTeams.importTeam(text, Dex);

// Pack into Showdown's internal team format
if (!teamObj) {
  console.error('Failed to parse team file.');
  process.exit(2);
}

// Pack into Showdown's internal team format
const packed = teamObj.pack();

console.log(packed);
