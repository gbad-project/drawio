import js from "@eslint/js";

export default [
  js.configs.recommended,
  {
    ignores: ["pyodide/", "dist/", ".venv/"],
  },
  {
    languageOptions: {
      globals: {
        Draw: "readonly",
        mxConstants: "readonly",
        mxUtils: "readonly",
        mxResources: "readonly",
      },
    },
  },
];
