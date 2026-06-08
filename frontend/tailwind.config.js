/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['Syne', 'sans-serif'],
        body: ['DM Sans', 'sans-serif'],
        mono: ['IBM Plex Mono', 'monospace'],
      },
      colors: {
        risk: {
          low:     '#22c55e',
          medium:  '#f59e0b',
          high:    '#ef4444',
          blocked: '#7c3aed',
        },
      },
    },
  },
  plugins: [],
}
