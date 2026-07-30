import type { Meta, StoryObj } from "@storybook/react-vite";
import { DatabaseSchemaModal, type SchemaTable } from "./DatabaseSchemaModal";

const meta = {
  title: "Components/DatabaseSchemaModal",
  component: DatabaseSchemaModal,
  args: {
    open: true,
    onClose: () => {},
  },
} satisfies Meta<typeof DatabaseSchemaModal>;

export default meta;
type Story = StoryObj<typeof meta>;

const SAMPLE_TABLES: SchemaTable[] = [
  {
    name: "courier",
    columns: [
      { name: "id", type: "uuid", primaryKey: true },
      { name: "name", type: "varchar" },
      { name: "status", type: "varchar" },
    ],
  },
  {
    name: "trip",
    columns: [
      { name: "id", type: "uuid", primaryKey: true },
      { name: "courier_id", type: "uuid", references: "courier.id" },
      { name: "status", type: "varchar" },
    ],
  },
  {
    name: "address_grant",
    columns: [
      { name: "id", type: "uuid", primaryKey: true },
      { name: "trip_id", type: "uuid", references: "trip.id" },
      { name: "line1", type: "varchar" },
    ],
  },
];

export const Populated: Story = {
  args: { databaseName: "dispatch", tables: SAMPLE_TABLES },
};

export const SingleTable: Story = {
  args: { databaseName: "kitchen", tables: [SAMPLE_TABLES[0]] },
};
