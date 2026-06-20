/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17202a",
        panel: "#f7f8fa",
        line: "#d8dee7",
        mint: "#0f8b8d",
        amber: "#b26a00",
        rose: "#b42318"
      }
    }
  },
  plugins: []
};
