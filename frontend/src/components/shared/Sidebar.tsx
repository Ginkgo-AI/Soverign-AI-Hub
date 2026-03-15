"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import Logo from "./Logo";
import { SettingsPanel } from "./SettingsPanel";
import {
  MessageSquare,
  Search,
  Boxes,
  Bot,
  Settings,
} from "lucide-react";

const DOCK_ITEMS = [
  { href: "/chat", icon: MessageSquare, label: "Chat" },
  { href: "/collections", icon: Search, label: "Knowledge Base" },
  { href: "/models", icon: Boxes, label: "Models" },
  { href: "/agents", icon: Bot, label: "Agents" },
];

export default function Sidebar() {
  const pathname = usePathname() ?? "/";
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <>
      <aside className="w-12 border-r border-[var(--color-border)] bg-[var(--color-surface)] flex flex-col shrink-0 items-center relative">
        {/* Gradient top accent */}
        <div className="absolute top-0 left-0 right-0 h-[1px]" style={{ background: "var(--gradient-accent)" }} />

        {/* Logo */}
        <div className="py-3 flex items-center justify-center">
          <a href="/chat" title="Home">
            <Logo size={24} compact />
          </a>
        </div>

        {/* Separator */}
        <div className="w-6 h-px bg-[var(--color-border)] mb-1" />

        {/* Primary nav */}
        <nav className="flex-1 flex flex-col items-center gap-0.5 py-1">
          {DOCK_ITEMS.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <a
                key={item.href}
                href={item.href}
                title={item.label}
                className={`relative flex items-center justify-center w-9 h-9 rounded-lg transition-all
                  ${active
                    ? "text-white bg-white/[0.08]"
                    : "text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-white/[0.04]"
                  }`}
              >
                {active && (
                  <div
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-3 rounded-full"
                    style={{ background: "var(--gradient-accent)" }}
                  />
                )}
                <item.icon size={18} className={active ? "text-[var(--color-accent)]" : ""} />
              </a>
            );
          })}
        </nav>

        {/* Separator */}
        <div className="w-6 h-px bg-[var(--color-border)] mb-1" />

        {/* Settings gear */}
        <div className="py-3">
          <button
            onClick={() => setSettingsOpen(true)}
            title="Settings & Admin"
            className={`flex items-center justify-center w-9 h-9 rounded-lg transition-all
              text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-white/[0.04]
              ${settingsOpen ? "text-white bg-white/[0.08]" : ""}`}
          >
            <Settings size={18} />
          </button>
        </div>
      </aside>

      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  );
}
