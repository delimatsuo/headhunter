module.exports = {
  root: true,
  env: {
    es6: true,
    node: true,
  },
  extends: [
    "eslint:recommended",
    "@typescript-eslint/recommended",
  ],
  parser: "@typescript-eslint/parser",
  parserOptions: {
    project: ["tsconfig.json", "tsconfig.dev.json"],
    sourceType: "module",
  },
  ignorePatterns: [
    "/lib/**/*", // Ignore built files.
    "/generated/**/*", // Ignore generated files.
  ],
  plugins: [
    "@typescript-eslint",
    "import",
  ],
  rules: {
    "quotes": ["error", "double"],
    "import/no-unresolved": 0,
    "indent": ["error", 2],
    "@typescript-eslint/no-unused-vars": ["error", { "argsIgnorePattern": "^_" }],
    "max-len": ["error", { "code": 120 }],
    "no-restricted-imports": [
      "error",
      {
        "paths": [
          {
            "name": "@google-cloud/aiplatform",
            "message": "Gemini enrichment is disabled in Functions. Use Together AI Python processors for enrichment."
          }
        ],
        "patterns": [
          {
            "group": ["**/*gemini*", "**/*Gemini*"],
            "message": "Do not add Gemini enrichment code to Functions."
          }
        ]
      }
    ],
  },
};
