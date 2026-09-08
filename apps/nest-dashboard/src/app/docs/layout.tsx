import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Docs",
  description:
    "Install Nanda Town with pip install nest-core, run your first multi-agent experiment, learn the scenario YAML format and the twelve protocol layers, write a plugin, and run agents in the cloud.",
  alternates: { canonical: "/docs" },
};

const softwareJsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "Nanda Town (nest-core)",
  applicationCategory: "DeveloperApplication",
  operatingSystem: "macOS, Linux, Windows",
  description:
    "Open-source multi-agent simulator: run deterministic scenarios of AI agents, write layer plugins, and validate agent protocols.",
  url: "https://nandatown.projectnanda.org/docs",
  installUrl: "https://pypi.org/project/nest-core/",
  offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
  publisher: { "@type": "Organization", name: "Project NANDA" },
};

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(softwareJsonLd) }}
      />
      {children}
    </>
  );
}
