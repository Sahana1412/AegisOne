/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ['class'],
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // AegisOne brand palette
        aegis: {
          bg: '#050a14',
          surface: '#0a1628',
          border: '#1a2d4a',
          accent: '#00d4ff',
          'accent-dim': '#0099bb',
          critical: '#ff3b3b',
          high: '#ff8c00',
          medium: '#f5c518',
          low: '#00c851',
          info: '#4a9eff',
          muted: '#4a6080',
          text: '#e2e8f0',
          'text-dim': '#8fa3bf',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      backgroundImage: {
        'grid-pattern': 'linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px)',
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'aegis-gradient': 'linear-gradient(135deg, #050a14 0%, #0a1628 50%, #050a14 100%)',
      },
      backgroundSize: {
        'grid': '40px 40px',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'scan': 'scan 2s linear infinite',
        'blink': 'blink 1.5s step-end infinite',
        'slide-in': 'slideIn 0.3s ease-out',
        'fade-in': 'fadeIn 0.4s ease-out',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        scan: {
          '0%': { backgroundPosition: '0 -100%' },
          '100%': { backgroundPosition: '0 100%' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        slideIn: {
          '0%': { transform: 'translateX(-10px)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        glow: {
          '0%': { boxShadow: '0 0 5px rgba(0,212,255,0.3)' },
          '100%': { boxShadow: '0 0 20px rgba(0,212,255,0.6)' },
        },
      },
      boxShadow: {
        'aegis': '0 0 0 1px rgba(0,212,255,0.2), 0 4px 16px rgba(0,212,255,0.1)',
        'aegis-lg': '0 0 0 1px rgba(0,212,255,0.3), 0 8px 32px rgba(0,212,255,0.15)',
        'critical': '0 0 0 1px rgba(255,59,59,0.3), 0 4px 16px rgba(255,59,59,0.1)',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
