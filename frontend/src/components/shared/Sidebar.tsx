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
      <aside className="w-[52px] bg-[var(--color-bg)] flex flex-col shrink-0 items-center border-r border-[var(--color-border)]">
        {/* Logo */}
        <div className="h-14 flex items-center justify-center">
          <a href="/chat" title="Home" className="opacity-80 hover:opacity-100 transition-opacity">
            <Logo size={22} compact />
          </a>
        </div>

        {/* Primary nav */}
        <nav className="flex-1 flex flex-col items-center gap-1 py-2">
          {DOCK_ITEMS.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <a
                key={item.href}
                href={item.href}
                title={item.label}
                className={`relative flex items-center justify-center w-9 h-9 rounded-xl transition-all
                  ${active
                    ? "text-[var(--color-text)] bg-[var(--color-surface-hover)]"
                    : "text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] hover:bg-[var(--color-surface)]"
                  }`}
              >
                {active && (
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-4 rounded-full bg-[var(--color-accent)]" />
                )}
                <item.icon size={17} strokeWidth={active ? 2 : 1.5} />
              </a>
            );
          })}
        </nav>

        {/* Settings */}
        <div className="py-3">
          <button
            onClick={() => setSettingsOpen(true)}
            title="Settings & Admin"
            className={`flex items-center justify-center w-9 h-9 rounded-xl transition-all
              ${settingsOpen
                ? "text-[var(--color-text)] bg-[var(--color-surface-hover)]"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] hover:bg-[var(--color-surface)]"
              }`}
          >
            <Settings size={17} strokeWidth={1.5} />
          </button>
        </div>
      </aside>

      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  );
}
