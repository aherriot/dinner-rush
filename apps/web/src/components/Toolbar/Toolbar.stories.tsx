import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { ActionMenu, SegmentedControl, ToggleGroup, Toolbar } from "./Toolbar";

const SPEEDS = [
  { value: "1", label: "1×" },
  { value: "10", label: "10×" },
  { value: "60", label: "60×" },
];

function SpeedDemo(props: { disabled?: boolean }) {
  const [speed, setSpeed] = useState("1");
  return <SegmentedControl label="Speed" options={SPEEDS} value={speed} onChange={setSpeed} {...props} />;
}

const STATIONS = [
  { value: "oven", label: "Oven" },
  { value: "prep", label: "Prep" },
  { value: "box", label: "Box" },
];

function StationDemo(props: { disabled?: boolean }) {
  const [selected, setSelected] = useState<string[]>(["oven"]);
  return <ToggleGroup options={STATIONS} selected={selected} onChange={setSelected} {...props} />;
}

const meta = {
  title: "Components/Toolbar",
} satisfies Meta;

export default meta;
type Story = StoryObj<typeof meta>;

export const SegmentedControlStory: Story = {
  name: "Segmented control",
  render: () => <SpeedDemo />,
};

export const ToggleGroupStory: Story = {
  name: "Toggle group",
  render: () => <StationDemo />,
};

export const Disabled: Story = {
  render: () => (
    <Toolbar>
      <SpeedDemo disabled />
      <StationDemo disabled />
    </Toolbar>
  ),
};

export const WithActionMenu: Story = {
  name: "With action menu (chaos scenarios)",
  render: () => (
    <Toolbar>
      <SpeedDemo />
      <ActionMenu
        label="Chaos"
        items={[
          { key: "friday_rush", label: "Friday rush", onSelect: () => {} },
          { key: "dispatch_down", label: "Dispatch down", onSelect: () => {} },
          { key: "oven_outage", label: "Oven outage", onSelect: () => {} },
        ]}
      />
    </Toolbar>
  ),
};
