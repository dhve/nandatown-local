import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Visualizer",
  description:
    "Load a Nanda Town simulation trace and watch AI agents interact — message flows, agent timelines, and playback controls in the browser.",
  alternates: { canonical: "/visualizer" },
};

export default function VisualizerLayout({ children }: { children: React.ReactNode }) {
  return children;
}
