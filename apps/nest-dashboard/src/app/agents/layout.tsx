import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Agents",
  description:
    "A live demo of the Nanda Town agent network — explore the agents that populate the sandbox and how they connect.",
  alternates: { canonical: "/agents" },
};

export default function AgentsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
