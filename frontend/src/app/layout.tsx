import type { Metadata } from "next";
import "./globals.css";
import ClassificationBanner from "@/components/shared/ClassificationBanner";
import {
  MessageSquare,
  Code2,
  Database,
  Bot,
  GitBranch,
  Boxes,
  Shield,
  Users,
  FileText,
  Lock,
  ClipboardCheck,
  Radio,
  Settings,
  User,
} from "lucide-react";

export const metadata: Metadata = {
  title: "Sovereign AI Hub",
  description: "Air-gapped, locally-run AI platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[var(--color-bg)] text-[var(--color-text)] min-h-screen">
        <ClassificationBanner />
        <div className="flex h-screen" style={{ paddingBottom: "22px" }}>
          {/* Global sidebar — hidden on chat page (which has its own) */}
          <Sidebar />

          {/* Main content */}
          <main className="flex-1 overflow-hidden">{children}</main>
        </div>
      </body>
    </html>
  );
}

function Sidebar() {
  return (
    <aside className="w-56 border-r border-[var(--color-border)] bg-[var(--color-surface)] flex flex-col shrink-0">
      <div className="p-4 border-b border-[var(--color-border)]">
        <a href="/" className="block">
          <h1 className="text-lg font-semibold tracking-tight">
            Sovereign AI
          </h1>
          <p className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
            Local &middot; Private &middot; Secure
          </p>
        </a>
      </div>
      <nav className="flex-1 p-2 space-y-0.5">
        <NavItem href="/chat" label="Chat" icon={<MessageSquare size={16} />} />
        <NavItem href="/code" label="Code" icon={<Code2 size={16} />} />
        <NavItem href="/collections" label="Knowledge Base" icon={<Database size={16} />} />
        <NavItem href="/agents" label="Agents" icon={<Bot size={16} />} />
        <NavItem href="/workflows" label="Workflows" icon={<GitBranch size={16} />} />
        <NavItem href="/models" label="Models" icon={<Boxes size={16} />} />
      </nav>
      <div className="p-2 border-t border-[var(--color-border)] space-y-0.5">
        <NavItem href="/admin" label="Admin" icon={<Shield size={16} />} />
        <SubNavItem href="/admin/users" label="Users" icon={<Users size={14} />} />
        <SubNavItem href="/admin/audit" label="Audit" icon={<FileText size={14} />} />
        <SubNavItem href="/admin/security" label="Security" icon={<Lock size={14} />} />
        <SubNavItem href="/admin/compliance" label="Compliance" icon={<ClipboardCheck size={14} />} />
        <SubNavItem href="/admin/edge" label="Edge Devices" icon={<Radio size={14} />} />
        <NavItem href="/settings" label="Settings" icon={<Settings size={16} />} />
        <NavItem href="/login" label="Account" icon={<User size={16} />} />
      </div>
    </aside>
  );
}

function NavItem({
  href,
  label,
  icon,
}: {
  href: string;
  label: string;
  icon: React.ReactNode;
}) {
  return (
    <a
      href={href}
      className="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
    >
      <span className="shrink-0 opacity-70">{icon}</span>
      {label}
    </a>
  );
}

function SubNavItem({
  href,
  label,
  icon,
}: {
  href: string;
  label: string;
  icon: React.ReactNode;
}) {
  return (
    <a
      href={href}
      className="flex items-center gap-2 pl-7 pr-3 py-1.5 rounded-md text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
    >
      <span className="shrink-0 opacity-60">{icon}</span>
      {label}
    </a>
  );
}
