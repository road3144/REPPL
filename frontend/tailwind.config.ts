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
        mint: '#34d399',
        brand: '#4a6cf7',
        'brand-dark': '#3a5ce5',
        'brand-light': '#7a9cff',
      },
      boxShadow: {
        glow: '0 0 60px rgba(14,165,233,0.25)',
        'brand-sm': '0 4px 16px rgba(74,108,247,0.18)',
        'brand-lg': '0 8px 40px rgba(74,108,247,0.25)',
      }
    }
  },
  plugins: []
} satisfies Config;
