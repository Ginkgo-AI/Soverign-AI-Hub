export default function AdminPage() {
  return (
    <div className="p-6">
      <h2 className="text-2xl font-semibold mb-4">Admin</h2>
      <div className="grid grid-cols-3 gap-4">
        <a href="/admin/users" className="p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)]">
          <h3 className="font-medium">Users</h3>
          <p className="text-xs text-[var(--color-text-muted)] mt-1">Manage users and roles</p>
        </a>
        <a href="/admin/audit" className="p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)]">
          <h3 className="font-medium">Audit Log</h3>
          <p className="text-xs text-[var(--color-text-muted)] mt-1">View all system activity</p>
        </a>
        <a href="/settings" className="p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)]">
          <h3 className="font-medium">Settings</h3>
          <p className="text-xs text-[var(--color-text-muted)] mt-1">System configuration</p>
        </a>
      </div>
    </div>
  );
}
