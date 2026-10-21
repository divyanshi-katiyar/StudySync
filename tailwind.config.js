/** Design tokens for StudySync. See README, "Design system". */
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#14213D', // text, dark surfaces
        paper: '#F4F6FA', // page background
        line: '#D7DCE6', // borders and dividers
        muted: '#4F5A73', // secondary text (7:1 on paper)
        marker: { DEFAULT: '#2F4FCF', dark: '#2440AD', soft: '#E4E9FB' }, // primary actions
        hilite: { DEFAULT: '#FFE45C', soft: '#FFF6BF' }, // the highlighter: marks what is new or active
        danger: { DEFAULT: '#B42318', soft: '#FDE8E6' },
        success: { DEFAULT: '#1A7F4B', soft: '#DDF3E7' },
      },
      fontFamily: {
        display: ['"Bricolage Grotesque Variable"', 'system-ui', 'sans-serif'],
        sans: ['"Public Sans Variable"', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        pop: '0 12px 32px -8px rgba(20,33,61,.28)',
      },
    },
  },
  plugins: [],
}
