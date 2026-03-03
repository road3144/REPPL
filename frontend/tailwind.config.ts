import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: '#0f172a',
        card: '#111827',
        accent: '#0ea5e9',
        accentWarm: '#f97316',
        mint: '#34d399'
      },
      boxShadow: {
        glow: '0 0 60px rgba(14,165,233,0.25)'
      }
    }
  },
  plugins: []
} satisfies Config;
