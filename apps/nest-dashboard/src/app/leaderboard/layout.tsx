import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Leaderboard",
  description:
    "Scores for NandaHack hackathon submissions — community plugins for the twelve Nanda Town protocol layers, ranked by the judge panel.",
  alternates: { canonical: "/leaderboard" },
};

export default function LeaderboardLayout({ children }: { children: React.ReactNode }) {
  return children;
}
