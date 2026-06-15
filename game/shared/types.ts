// Shared types between the Colyseus server and the Expo client.
// Keep this file dependency-free so both sides can import it directly.

export type Role = "crewmate" | "impostor";

export type Phase =
  | "lobby" // waiting for players, host can start
  | "playing" // free roam, tasks + kills happen
  | "meeting" // discussion + voting after a report / emergency
  | "ended"; // a team has won

export type WinReason =
  | "tasks" // crew finished all tasks
  | "vote" // impostors voted out
  | "kills" // impostors reached parity
  | "eject"; // crew ejected the last impostor / impostor ejected crew

// Messages the client sends to the server.
export type ClientMessage =
  | { type: "move"; dx: number; dy: number } // normalized joystick vector, -1..1
  | { type: "task"; taskId: string }
  | { type: "kill"; targetId: string }
  | { type: "report" }
  | { type: "emergency" }
  | { type: "vote"; targetId: string | null } // null = skip
  | { type: "start" }; // host only

// Tunables shared so client-side prediction matches the server.
export const GAME_CONFIG = {
  mapWidth: 1600,
  mapHeight: 1000,
  playerRadius: 24,
  moveSpeed: 220, // px per second
  killCooldownMs: 25_000,
  killRange: 90,
  reportRange: 120,
  meetingDurationMs: 45_000,
  emergencyCooldownMs: 20_000,
  minPlayers: 4,
  maxPlayers: 12,
  tasksPerPlayer: 4,
} as const;
