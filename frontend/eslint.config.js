import js from "@eslint/js";
import prettier from "eslint-config-prettier";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";

const STORAGE_MSG =
  "Tokens live in memory and the PKCE verifier in sessionStorage; localStorage is banned.";
const API_IMPORT_MSG =
  "api/ is the bottom layer: it imports the generated types and @/types, never app/, components/, lib/, rules/ or screens/.";
const COMPONENT_IMPORT_MSG =
  "A component knows nothing about the API or a rule: it never imports api/, app/, rules/ or screens/.";
const LIB_IMPORT_MSG =
  "lib/ is infrastructure: it never imports app/, components/, rules/ or screens/.";
const RULE_IMPORT_MSG =
  "A rule is a pure function: it never imports the API client, React, app/ or a screen.";
const SCREEN_IMPORT_MSG =
  "A screen never imports app/ or another screen; a part two screens share moves up to their common folder.";

export default defineConfig([
  { ignores: ["dist", "src/api/generated"] },
  js.configs.recommended,
  tseslint.configs.strictTypeChecked,
  tseslint.configs.stylisticTypeChecked,
  jsxA11y.flatConfigs.recommended,
  reactHooks.configs.flat.recommended,
  reactRefresh.configs.vite,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      parserOptions: {
        projectService: {
          allowDefaultProject: ["vite.config.ts"],
        },
        tsconfigRootDir: import.meta.dirname,
      },
    },
    linterOptions: {
      noInlineConfig: true,
      reportUnusedDisableDirectives: "error",
    },
    rules: {
      complexity: ["error", 8],
      "no-nested-ternary": "error",
      "no-restricted-globals": ["error", { message: STORAGE_MSG, name: "localStorage" }],
      "no-restricted-properties": [
        "error",
        { message: STORAGE_MSG, object: "globalThis", property: "localStorage" },
        { message: STORAGE_MSG, object: "window", property: "localStorage" },
      ],
      "no-warning-comments": ["error", { location: "anywhere", terms: ["fixme", "hack", "todo"] }],
    },
  },
  {
    files: ["src/app/shell/**/*.tsx", "src/components/**/*.tsx", "src/screens/**/*.tsx"],
    ignores: ["**/*.test.tsx"],
    rules: {
      "max-lines": ["warn", { max: 100, skipBlankLines: true, skipComments: true }],
    },
  },
  {
    files: ["src/api/**/*.{ts,tsx}"],
    ignores: ["**/*.test.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/app/**", "@/components/**", "@/lib/**", "@/rules/**", "@/screens/**"],
              message: API_IMPORT_MSG,
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/components/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/api/**", "@/app/**", "@/rules/**", "@/screens/**"],
              message: COMPONENT_IMPORT_MSG,
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/lib/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/app/**", "@/components/**", "@/rules/**", "@/screens/**"],
              message: LIB_IMPORT_MSG,
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/screens/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        { patterns: [{ group: ["@/app/**", "@/screens/**"], message: SCREEN_IMPORT_MSG }] },
      ],
    },
  },
  {
    files: ["src/**/rules.ts", "src/rules/**/*.ts"],
    ignores: ["**/*.test.ts"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          paths: [{ message: RULE_IMPORT_MSG, name: "react" }],
          patterns: [
            {
              group: [
                "@/api/client",
                "@/api/media",
                "@/api/queries",
                "@/app/**",
                "@/screens/**",
                "@tanstack/*",
              ],
              message: RULE_IMPORT_MSG,
            },
          ],
        },
      ],
    },
  },
  {
    files: ["**/*.js"],
    extends: [tseslint.configs.disableTypeChecked],
  },
  prettier,
]);
