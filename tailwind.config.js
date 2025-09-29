/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./*.html",
    "./**/templates/**/*.html", // Scans HTML files in your root folder
    "./templates/**/*.html", // Scans HTML files in a 'templates' folder (adjust if needed)
    "./templates/**/*.html", // Scans HTML files in a 'templates' folder (adjust if needed)
    "./survey/templates/**/**/*.html", // CRITICAL: This lets Tailwind see Flowbite's classes
    "./node_modules/flowbite/**/*.js", // For Flowbite's JS
  ],
  theme: {
    extend: {
      // Step 3a: Define the "cupcake" primary palette for Flowbite
      colors: {
        primary: {
          50: "#f0f9fa",
          100: "#e0f2f5",
          200: "#bfe5eb",
          300: "#9fd8e1",
          400: "#7ecbd7",
          500: "#65c3c8",
          600: "#5cb0b5",
          700: "#4d9499",
          800: "#3e777c",
          900: "#305a5f",
          950: "#213d41",
        },
      },
    },
  },

  // Step 3b: Add the plugins
  plugins: [
    require("flowbite/plugin"),
    require("daisyui"),
    // for line clamping
    require("@tailwindcss/line-clamp"),
  ],
};
