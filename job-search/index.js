#!/usr/bin/env node
// Job search tool for Christian McMahan.
//
// Usage:
//   node index.js                         # rank all seed jobs, print report
//   node index.js --sectors golf,finance  # filter by sector(s)
//   node index.js --geos AE,GB,US          # filter by geography(ies)
//   node index.js --links                  # also print live search links to run
//   node index.js --md > report.md         # write a clean markdown report
//
// Set ANTHROPIC_API_KEY to use Claude for ranking; otherwise a heuristic runs.

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { rankJobs } from './rank.js';
import { GEOGRAPHIES, SECTORS, buildSearchPlan, searchLinks } from './tracks.js';
import { passesLevelRule, parseSalary, attainability } from './filters.js';

const __dir = dirname(fileURLToPath(import.meta.url));
const profile = JSON.parse(readFileSync(join(__dir, 'profile.json'), 'utf8'));
const seed = JSON.parse(readFileSync(join(__dir, 'seed-jobs.json'), 'utf8'));

function parseArgs(argv) {
  const args = { sectors: null, geos: null, links: false, md: false, allLevels: false, realistic: false };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--links') args.links = true;
    else if (a === '--md') args.md = true;
    else if (a === '--all-levels') args.allLevels = true;
    else if (a === '--realistic') args.realistic = true;
    else if (a === '--sectors') args.sectors = argv[++i]?.split(',').map((s) => s.trim());
    else if (a === '--geos') args.geos = argv[++i]?.split(',').map((s) => s.trim().toUpperCase());
  }
  return args;
}

function flagBadge(flags = []) {
  const map = {
    'high-wage': '💰 high-wage',
    benefits: '🎁 benefits',
    abroad: '✈️ abroad',
    'entry-level-friendly': '🌱 entry-level',
    'great-sector-fit': '🎯 sector fit',
    'stretch-role': '📈 stretch',
    'needs-license': '📜 needs license',
  };
  return flags.map((f) => map[f] || f).join(' · ');
}

function bar(score) {
  const n = Math.round(score / 10);
  return '█'.repeat(n) + '░'.repeat(10 - n);
}

async function main() {
  const args = parseArgs(process.argv);

  let jobs = seed.jobs;
  if (args.sectors) jobs = jobs.filter((j) => args.sectors.includes(j.sector));
  if (args.geos) jobs = jobs.filter((j) => args.geos.includes(j.geo));

  // Christian's rule: finance & real estate must be entry-level (golf any level).
  const total = jobs.length;
  if (!args.allLevels) jobs = jobs.filter(passesLevelRule);
  const dropped = total - jobs.length;

  // --realistic hides the elite "Reach" seats so the list is just what's
  // genuinely attainable for the current resume.
  if (args.realistic) jobs = jobs.filter((j) => attainability(j).tier !== 'Reach');

  const { ranked, engine } = await rankJobs(jobs);

  const out = [];
  out.push(`# Job Search Report — ${profile.name}`);
  out.push('');
  out.push(`**Profile:** ${profile.education.degree}, ${profile.education.school} (grad ${profile.education.graduation}) · ${profile.citizenship} citizen`);
  out.push(`**Priorities:** high wage · good benefits · open to abroad · sectors: ${profile.preferences.target_sectors.join(', ')}`);
  out.push(`**Listings ranked:** ${ranked.length} · **Ranking engine:** ${engine} · **Data fetched:** ${seed.fetched_at}`);
  out.push(`**Level rule:** ${args.allLevels ? 'all levels (filter off)' : `finance & real estate restricted to entry-level — ${dropped} non-entry role(s) hidden`}`);
  out.push('');
  out.push('## Top matches');
  out.push('');

  ranked.forEach((j, i) => {
    out.push(`### ${i + 1}. ${j.title} — ${j.company}`);
    out.push(`\`${bar(j.fitScore)}\` **${j.fitScore}/100**  ${flagBadge(j.flags)}`);
    out.push('');
    const sal = parseSalary(j.compensation);
    const wage = sal ? `💵 ${j.compensation}` : `comp: ${j.compensation}`;
    const { tier, why } = attainability(j);
    const tierIcon = { Realistic: '🟢', Stretch: '🟡', Reach: '🔴' }[tier];
    out.push(`- 📍 ${j.location} (${GEOGRAPHIES[j.geo]?.label || j.geo}) · ${j.type} · ${wage}`);
    out.push(`- ${tierIcon} **${tier}** — ${why}`);
    out.push(`- 💬 ${j.rationale}`);
    out.push(`- 🔗 [Apply / view](${j.url})`);
    out.push('');
  });

  // Work-authorization cheat sheet for the geographies in play.
  const geosInPlay = [...new Set(ranked.map((j) => j.geo))];
  out.push('## Work authorization (Canadian citizen)');
  out.push('');
  for (const geo of geosInPlay) {
    const g = GEOGRAPHIES[geo];
    if (!g) continue;
    out.push(`- **${g.label}** — ${g.work_authorization}. _${g.tax_note}._`);
  }
  out.push('');

  if (args.links) {
    out.push('## Live search links (run these yourself)');
    out.push('');
    const plan = buildSearchPlan({ sectors: args.sectors, geos: args.geos });
    for (const p of plan) {
      const q = p.queries[0];
      const l = searchLinks(q, p.geo);
      out.push(`- **${p.sectorLabel} · ${p.geoLabel}** — [Indeed](${l.indeed}) · [LinkedIn](${l.linkedin})`);
    }
    out.push('');
  }

  process.stdout.write(out.join('\n') + '\n');
}

main().catch((e) => {
  console.error('Error:', e.message);
  process.exit(1);
});
