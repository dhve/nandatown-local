import Image from "next/image";

const MARITIME_URL = "https://maritime.sh";

/**
 * Quiet partner callout: a slim clickable row pointing at Maritime,
 * our preferred partner for hosting AI agents. Used sparingly, only
 * where running agents in the cloud is genuinely relevant.
 */
export function MaritimeCallout({
  title = "Want to try it with an agent in the cloud?",
  body = "Maritime is our preferred partner for hosting AI agents — 20 agents free with code NANDATOWN.",
  className = "",
}: {
  title?: string;
  body?: string;
  className?: string;
}) {
  return (
    <a
      href={MARITIME_URL}
      target="_blank"
      rel="noopener noreferrer"
      className={`group flex items-center gap-4 rounded-2xl border border-cream-400/70 bg-cream-50 px-5 py-4 transition-colors hover:border-ink-300 ${className}`}
    >
      <Image
        src="/brand/maritime.png"
        alt=""
        width={24}
        height={32}
        className="h-8 w-auto shrink-0 object-contain opacity-80 transition-opacity group-hover:opacity-100"
      />
      <span className="min-w-0 flex-1">
        <span className="block text-[0.95rem] font-medium leading-snug text-ink-900">
          {title}
        </span>
        <span className="mt-0.5 block text-[0.85rem] leading-snug text-ink-400">
          {body}
        </span>
      </span>
      <span className="shrink-0 font-mono text-[10px] uppercase tracking-[0.22em] text-ink-400 transition-colors group-hover:text-rust">
        maritime.sh &rarr;
      </span>
    </a>
  );
}
