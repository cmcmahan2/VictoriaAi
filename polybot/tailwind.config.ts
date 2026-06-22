import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // OddsJam-ish dark palette
        ink: "#0a0e14",
        panel: "#0f1620",
        card: "#121b27",
        edge: "#1c2735",
        muted: "#7d8ba0",
        pos: "#34d399",
        posDim: "#1f3d33",
        warn: "#fbbf24",
        neg: "#f87171",
      },
    },
  },
  plugins: [],
};

export default config;
