import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import jsxA11y from "eslint-plugin-jsx-a11y";
import storybook from "eslint-plugin-storybook";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "storybook-static", "src/design/tokens.css", "src/design/tokens.ts", "src/design/tokens.storybook.ts"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommended,
      reactRefresh.configs.vite,
      jsxA11y.flatConfigs.recommended,
    ],
    plugins: {
      "react-hooks": reactHooks,
    },
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
    },
    rules: {
      ...reactHooks.configs["recommended-latest"].rules,
      // DESIGN.md §9.3 — no component may set colour via inline style;
      // semantic tokens in component CSS are the only sanctioned path.
      "no-restricted-syntax": [
        "error",
        {
          selector:
            "JSXAttribute[name.name='style'] JSXExpressionContainer ObjectExpression > Property[key.name=/^(color|background|backgroundColor|border|borderColor|fill|stroke)$/]",
          message:
            "No inline colour styles — use a semantic token in a Component.module.css file instead (DESIGN.md §9).",
        },
      ],
    },
  },
  ...storybook.configs["flat/recommended"],
);
