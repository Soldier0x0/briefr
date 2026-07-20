import js from "@eslint/js";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import prettier from "eslint-config-prettier";

/**
 * F1.1 / Phase 1 W6 — incremental ESLint gate.
 *
 * Required scope: `src/scoring/**` + `src/pages/admin/**`
 * Deferred: full `src/**`, prettier --check / format-only PR, max-lines.
 *
 * Lenient on purpose: catch no-undef + rules-of-hooks; do not fail the tree
 * on React Compiler-era set-state-in-effect / purity rules or unused locals.
 */
const gatedFiles = ["src/scoring/**/*.{js,jsx}", "src/pages/admin/**/*.{js,jsx}"];

export default [
  {
    ignores: [
      "dist/**",
      "node_modules/**",
      "coverage/**",
      "**/*.min.js",
    ],
  },
  {
    files: gatedFiles,
    ...js.configs.recommended,
  },
  {
    files: gatedFiles,
    plugins: {
      react,
      "react-hooks": reactHooks,
    },
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: "module",
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
      globals: {
        window: "readonly",
        document: "readonly",
        navigator: "readonly",
        console: "readonly",
        localStorage: "readonly",
        sessionStorage: "readonly",
        fetch: "readonly",
        URL: "readonly",
        URLSearchParams: "readonly",
        FormData: "readonly",
        Blob: "readonly",
        File: "readonly",
        FileReader: "readonly",
        AbortController: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        setInterval: "readonly",
        clearInterval: "readonly",
        requestAnimationFrame: "readonly",
        cancelAnimationFrame: "readonly",
        IntersectionObserver: "readonly",
        ResizeObserver: "readonly",
        MutationObserver: "readonly",
        CustomEvent: "readonly",
        Event: "readonly",
        HTMLElement: "readonly",
        Node: "readonly",
        process: "readonly",
        // node:test unit tests colocated under these trees
        describe: "readonly",
        it: "readonly",
        test: "readonly",
        expect: "readonly",
        beforeEach: "readonly",
        afterEach: "readonly",
        before: "readonly",
        after: "readonly",
      },
    },
    settings: {
      react: { version: "detect" },
    },
    rules: {
      // React JSX — basics only (no prop-types enforcement).
      "react/jsx-uses-react": "off",
      "react/jsx-uses-vars": "error",
      "react/react-in-jsx-scope": "off",
      "react/prop-types": "off",
      // Hooks: classic safety only (not React Compiler / purity suite).
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      // Existing codebase — warn so the gate stays green without mass cleanup.
      "no-unused-vars": [
        "warn",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
          ignoreRestSiblings: true,
        },
      ],
      "no-useless-escape": "warn",
      "no-empty": ["error", { allowEmptyCatch: true }],
      "no-console": "off",
    },
  },
  prettier,
];
