"use client";

import { useEffect, useRef } from "react";
import {
  X,
  Database,
  Sparkles,
  GitBranch,
  Zap,
  Code2,
  Puzzle,
  Users,
  FileText,
  Lock,
  ClipboardCheck,
  Radio,
  Brain,
  User,
  Settings,
} from "lucide-react";

const NAV_LINKS = [
  { href: "/collections", label: "Knowledge Base", icon: Database },
  { href: "/skills", label: "Skills", icon: Sparkles },
  { href: "/workflows", label: "Workflows", icon: GitBranch },
  { href: "/automation", label: "Automation", icon: Zap },
  { href: "/code", label: "Code Editor", icon: Code2 },
];

const ADMIN_LINKS = [
  { href: "/admin/plugins", label: "Plugins", icon: Puzzle },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/audit", label: "Audit Log", icon: FileText },
  { href: "/admin/security", label: "Security", icon: Lock },
  { href: "/admin/compliance", label: "Compliance", icon: ClipboardCheck },
  { href: "/admin/edge", label: "Edge Devices", icon: Radio },
];

const SETTINGS_LINKS = [
  { href: "/settings/memory", label: "Memory Settings", icon: Brain },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/login", label: "Account", icon: User },
];

export function SettingsPanel({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (open) {
      document.addEventListener("keydown", handleKey);
      return () => document.removeEventListener("keydown", handleKey);
    }
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div
        ref={panelRef}
        className="fixed top-0 left-12 bottom-0 z-50 w-64 bg-[var(--color-surface)] border-r border-[var(--color-border)] shadow-2xl overflow-y-auto animate-slide-in"
        style={{ paddingTop: "22px", paddingBottom: "22px" }}
      >
        <div className="flex items-center justify-between px-4 py-4 border-b border-[var(--color-border)]">
          <h2 className="text-sm font-semibold">Settings & Admin</h2>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-white/5"
          >
            <X size={16} />
          </button>
        </div>

        <div className="px-2 py-3">
          <SectionLabel>Navigation</SectionLabel>
          {NAV_LINKS.map((item) => (
            <PanelLink key={item.href} href={item.href} icon={<item.icon size={16} />} label={item.label} />
          ))}
        </div>

        <div className="px-2 py-3 border-t border-[var(--color-border)]">
          <SectionLabel>Administration</SectionLabel>
          {ADMIN_LINKS.map((item) => (
            <PanelLink key={item.href} href={item.href} icon={<item.icon size={16} />} label={item.label} />
          ))}
        </div>

        <div className="px-2 py-3 border-t border-[var(--color-border)]">
          <SectionLabel>Settings</SectionLabel>
          {SETTINGS_LINKS.map((item) => (
            <PanelLink key={item.href} href={item.href} icon={<item.icon size={16} />} label={item.label} />
          ))}
        </div>
      </div>
    </>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--color-text-muted)] px-3 pt-2 pb-2 font-semibold">
      {children}
    </p>
  );
}

function PanelLink({
  href,
  icon,
  label,
}: {
  href: string;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <a
      href={href}
      className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-white/[0.04] transition-colors"
    >
      <span className="shrink-0 opacity-70">{icon}</span>
      {label}
    </a>
  );
}
