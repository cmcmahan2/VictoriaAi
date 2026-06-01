import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: [
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './modules/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          base: '#0d1117',
          card: '#161b22',
          card2: '#1c2128',
        },
        border: '#30363d',
        text: {
          primary: '#e6edf3',
          secondary: '#8b949e',
          muted: '#6e7681',
        },
        green: '#3fb950',
        red: '#f85149',
        blue: '#58a6ff',
        yellow: '#d29922',
        purple: '#bc8cff',
        orange: '#ffa657',
        accent: '#1f6feb',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};

export default config;
