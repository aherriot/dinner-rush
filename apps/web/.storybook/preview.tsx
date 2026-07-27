import type { Decorator, Preview } from "@storybook/react-vite";
import "../src/design/tokens.css";
import styles from "./preview.module.css";

const withTheme: Decorator = (Story, context) => {
  const theme = context.globals.theme ?? "dark";
  return (
    <div data-theme={theme} className={styles.canvas}>
      <Story />
    </div>
  );
};

const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    a11y: {
      // DESIGN.md §9.4: zero axe violations on both surfaces — enforced.
      test: "error",
    },
  },
  globalTypes: {
    theme: {
      description: "Dinner Rush colour theme",
      toolbar: {
        title: "Theme",
        icon: "circlehollow",
        items: [
          { value: "dark", icon: "circle", title: "Dark" },
          { value: "light", icon: "circlehollow", title: "Light" },
        ],
        dynamicTitle: true,
      },
    },
  },
  initialGlobals: {
    theme: "dark",
  },
  decorators: [withTheme],
};

export default preview;
