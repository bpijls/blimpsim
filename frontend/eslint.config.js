import js from "@eslint/js";
import react from "eslint-plugin-react";
import globals from "globals";

export default [
  js.configs.recommended,
  {
    files: ["src/**/*.{js,jsx}"],
    plugins: { react },
    languageOptions: {
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: { ...globals.browser, ...globals.vitest },
    },
    settings: { react: { version: "detect" } },
    rules: {
      // Marks components used in JSX as used; the rest of the plugin is not enabled.
      "react/jsx-uses-vars": "error",
    },
  },
];
