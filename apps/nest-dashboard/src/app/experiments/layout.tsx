import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Experiments",
  description:
    "Interactive in-browser multi-agent experiments — watch AI agents negotiate, coordinate, and trade in live Nanda Town scenarios.",
  alternates: { canonical: "/experiments" },
};

export default function ExperimentsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
