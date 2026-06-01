import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import bundled from "@/data/snapshot.json";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Locally: read the freshest snapshot from repo-root /macro/history (written by
// macro/history.py). When that filesystem isn't present (e.g. deployed on Vercel),
// fall back to the snapshot bundled with the app at macro-engine/data/snapshot.json.
export async function GET() {
  try {
    const dir = path.join(process.cwd(), "..", "macro", "history");
    if (fs.existsSync(dir)) {
      const files = fs.readdirSync(dir).filter((f) => f.endsWith(".json")).sort();
      if (files.length > 0) {
        const raw = fs.readFileSync(path.join(dir, files[files.length - 1]), "utf-8");
        return NextResponse.json({ snapshot: JSON.parse(raw), source: "live" });
      }
    }
  } catch {
    // fall through to bundled
  }
  return NextResponse.json({ snapshot: bundled, source: "bundled" });
}
