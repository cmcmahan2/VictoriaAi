# Game Design — "Sabotage" (working title)

An advanced social-deduction party game in the spirit of Among Us, built to ship on the
Apple App Store. Crewmates complete tasks and try to identify the impostors; impostors
sabotage, kill, and deceive their way to victory.

## Why this can be "more advanced than Among Us"

The base game is the proven Among Us loop. The differentiators we're building toward:

1. **Roles beyond crew/impostor** — Sheriff (can kill, but dies if wrong), Engineer (uses
   vents), Medic (one revive), Trickster (fake tasks), Seer (sees a role each meeting).
2. **Dynamic maps & sabotages** — reactor meltdown, comms blackout, door locks, lights.
3. **Proximity voice / text chat** — only hear players physically near you (huge for immersion).
4. **Persistent progression** — cosmetics, XP, ranked MMR, account system.
5. **AI-driven fill players** — when a lobby is short, Claude-driven bots that move, do tasks,
   and *argue in meetings* using natural language (this repo already centers on Claude — a
   genuine edge no competitor has).
6. **Replays & "detective" recap** — after a match, a timeline of who was where.

## Architecture

```
game/
  shared/   TypeScript types + tunables shared by client & server
  server/   Colyseus authoritative game server (Node) — source of truth
  app/      Expo (React Native) client — renders state, sends intents
```

The server is **authoritative**: clients send *intents* ("move this direction", "kill that
player") and the server validates them and broadcasts the resulting state. This is what stops
cheating — a hacked client can't teleport or kill out of range because the server rejects it.

## Core loop (the MVP we're scaffolding now)

1. Players join a room → **lobby**.
2. Host starts → server assigns roles + tasks, transitions to **playing**.
3. Crew walk the map and complete tasks; impostors kill (on cooldown).
4. Anyone can call an **emergency** meeting or **report** a body → **meeting**.
5. Players discuss and **vote**; most-voted player is ejected.
6. Server checks win conditions → back to **playing** or **ended**.

Win conditions:
- Crew win: all tasks done, or all impostors ejected.
- Impostors win: impostors >= crew (parity).

## Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| 0 | Scaffold: lobby, movement, roles, kill, meeting, vote, win check | ✅ this build |
| 1 | Real tasks (minigames), sabotage system, body reporting polish | next |
| 2 | Accounts, matchmaking, friend lobbies, reconnection | |
| 3 | Cosmetics + progression + IAP | |
| 4 | Proximity chat (voice via WebRTC) | |
| 5 | Claude AI fill-bots that play *and* argue in meetings | |
| 6 | App Store submission (TestFlight → review) | |

## Shipping to the App Store (what this requires beyond code)

- **Apple Developer Program** account ($99/yr).
- Build & sign via **EAS Build** (`eas build -p ios`) — no Mac required for the build itself.
- **TestFlight** for beta testing, then App Store review.
- A hosted server for Colyseus (Render/Fly.io/Railway) — the client points at its URL.
- Privacy policy + age rating (social games with chat need care here — likely 12+).

See `README.md` for how to run everything locally today.
