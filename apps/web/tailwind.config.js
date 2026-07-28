/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: "#0F2A4A",
        brandblue: "#1B6CA8",
        teal: "#1F8A70",
      },
    },
  },
  plugins: [],
};
