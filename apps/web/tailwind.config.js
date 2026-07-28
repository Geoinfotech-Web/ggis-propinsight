/** @type {import('tailwindcss').Config} */
import { ggisColors, ggisFontFamily } from "./src/theme.tokens.js";

export default {
  darkMode: ["selector", '[data-theme="dark"]'],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: ggisFontFamily,
      colors: ggisColors,
    },
  },
  plugins: [],
};
