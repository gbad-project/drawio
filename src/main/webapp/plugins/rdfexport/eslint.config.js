import js from "@eslint/js";

export default [
  js.configs.recommended,
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
