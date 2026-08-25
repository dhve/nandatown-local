import type { MetadataRoute } from "next";

const SITE_URL = "https://nandatown.projectnanda.org";

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();
  return [
    { url: SITE_URL, lastModified, changeFrequency: "weekly", priority: 1 },
    { url: `${SITE_URL}/docs`, lastModified, changeFrequency: "weekly", priority: 0.9 },
    { url: `${SITE_URL}/pravahack`, lastModified, changeFrequency: "weekly", priority: 0.9 },
    { url: `${SITE_URL}/skills`, lastModified, changeFrequency: "daily", priority: 0.8 },
    { url: `${SITE_URL}/prgallery`, lastModified, changeFrequency: "daily", priority: 0.8 },
    { url: `${SITE_URL}/experiments`, lastModified, changeFrequency: "weekly", priority: 0.7 },
    { url: `${SITE_URL}/leaderboard`, lastModified, changeFrequency: "daily", priority: 0.7 },
    { url: `${SITE_URL}/visualizer`, lastModified, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE_URL}/agents`, lastModified, changeFrequency: "monthly", priority: 0.6 },
  ];
}
