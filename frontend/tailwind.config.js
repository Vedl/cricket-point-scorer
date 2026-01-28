/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Aesthetic dark mode palette
        dark: {
          900: '#0f172a', // Slate 900
          800: '#1e293b', // Slate 800
          700: '#334155', // Slate 700
        },
        primary: {
          500: '#6366f1', // Indigo 500
          600: '#4f46e5', // Indigo 600
        }
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
