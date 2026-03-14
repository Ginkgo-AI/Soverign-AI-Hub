"use client";

interface VerifiedBadgeProps {
  verified?: boolean;
  tooltip?: string;
}

export function VerifiedBadge({ verified = true, tooltip }: VerifiedBadgeProps) {
  if (!verified) return null;

  return (
    <span
      className="inline-flex items-center gap-0.5 text-green-400"
      title={tooltip || "Cryptographically verified agent action"}
    >
      <svg
        width="12"
        height="12"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        <path d="M9 12l2 2 4-4" />
      </svg>
    </span>
  );
}
