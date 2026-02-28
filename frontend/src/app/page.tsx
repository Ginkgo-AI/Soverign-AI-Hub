export default function Home() {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center max-w-lg">
        <h2 className="text-3xl font-bold mb-4">Sovereign AI Hub</h2>
        <p className="text-[var(--color-text-muted)] mb-8">
          Enterprise AI capabilities with zero data exfiltration. Everything
          runs on your hardware.
        </p>
        <div className="grid grid-cols-2 gap-4">
          <DashboardCard
            href="/chat"
            title="Chat"
            description="Multi-turn conversations with local LLMs"
          />
          <DashboardCard
            href="/collections"
            title="Knowledge Base"
            description="Upload documents, ask questions, get cited answers"
          />
          <DashboardCard
            href="/agents"
            title="Agents"
            description="Autonomous task execution with tool calling"
          />
          <DashboardCard
            href="/models"
            title="Models"
            description="Manage, evaluate, and fine-tune local models"
          />
        </div>
      </div>
    </div>
  );
}

function DashboardCard({
  href,
  title,
  description,
}: {
  href: string;
  title: string;
  description: string;
}) {
  return (
    <a
      href={href}
      className="block p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)] transition-colors text-left"
    >
      <h3 className="font-semibold mb-1">{title}</h3>
      <p className="text-xs text-[var(--color-text-muted)]">{description}</p>
    </a>
  );
}
