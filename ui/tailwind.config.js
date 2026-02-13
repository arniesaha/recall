/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: {
          primary: '#0d0d0d',
          secondary: '#1a1a1a',
          tertiary: '#262626',
        },
        text: {
          primary: '#e5e5e5',
          secondary: '#a3a3a3',
        },
        accent: {
          DEFAULT: '#3b82f6',
          muted: '#1d4ed8',
        },
        border: '#333333',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
