import type { Metadata } from "next";
import "./globals.css";

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
        <div className="flex h-screen">
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
        <NavItem href="/chat" label="Chat" />
        <NavItem href="/code" label="Code" />
        <NavItem href="/collections" label="Knowledge Base" />
        <NavItem href="/agents" label="Agents" />
        <NavItem href="/workflows" label="Workflows" />
        <NavItem href="/models" label="Models" />
      </nav>
      <div className="p-2 border-t border-[var(--color-border)] space-y-0.5">
        <NavItem href="/admin" label="Admin" />
        <NavItem href="/settings" label="Settings" />
        <NavItem href="/login" label="Account" />
      </div>
    </aside>
  );
}

function NavItem({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      className="block px-3 py-2 rounded-md text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
    >
      {label}
    </a>
  );
}
