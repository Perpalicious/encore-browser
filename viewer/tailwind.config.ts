import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Geist Sans', 'Geist', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        serif: ['Newsreader', 'ui-serif', 'Georgia', 'serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      colors: {
        // Warm editorial palette (light)
        paper: '#FAF6EE',
        paper2: '#F3ECDD',
        ink: '#1A1612',
        ink2: '#544A3D',
        rule: '#E6DDC8',
        ember: '#B6502A',
        ember2: '#8B3A1A',
        // Dark mode — charcoal
        night: '#0F1012',
        night2: '#17181B',
        coal: '#1F2024',
        bone: '#ECEDEF',
        bone2: '#A0A2A8',
        dusk: '#2A2C31',
      },
      boxShadow: {
        card: '0 1px 0 rgba(26,22,18,0.04), 0 1px 2px rgba(26,22,18,0.04), 0 4px 12px -2px rgba(26,22,18,0.06)',
        cardHover: '0 1px 0 rgba(26,22,18,0.05), 0 8px 24px -6px rgba(26,22,18,0.14)',
        cardDark: '0 1px 0 rgba(0,0,0,0.4), 0 4px 12px -2px rgba(0,0,0,0.4)',
        pop: '0 12px 40px -10px rgba(26,22,18,0.25)',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        slideDown: {
          '0%': { opacity: '0', transform: 'translateY(-4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
      animation: {
        shimmer: 'shimmer 1.6s linear infinite',
        slideDown: 'slideDown 220ms cubic-bezier(.2,.7,.2,1)',
        fadeIn: 'fadeIn 280ms ease-out',
      },
    },
  },
  plugins: [],
};

export default config;
