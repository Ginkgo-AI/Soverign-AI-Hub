"use client";

import { useState } from "react";
import { useAuthStore } from "@/stores/authStore";
import { apiJson } from "@/lib/api";
import { Shield } from "lucide-react";

export default function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const { login } = useAuthStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    try {
      const endpoint = mode === "login" ? "/api/auth/login" : "/api/auth/register";
      const body =
        mode === "login"
          ? { email, password }
          : { email, password, name };

      const data = await apiJson<{
        access_token: string;
        user_id: string;
        name: string;
        role: string;
      }>(endpoint, {
        method: "POST",
        body: JSON.stringify(body),
      });

      login(data.access_token, data.user_id, data.name, data.role);
      window.location.href = "/chat";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    }
  };

  return (
    <div className="flex items-center justify-center h-full bg-gradient-subtle relative overflow-hidden">
      {/* Background pattern */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "radial-gradient(circle, var(--color-text) 1px, transparent 1px)",
          backgroundSize: "32px 32px",
        }}
      />

      <div className="w-full max-w-sm relative z-10">
        <div className="flex justify-center mb-4">
          <div className="p-3 rounded-full bg-[var(--color-accent)]/10 border border-[var(--color-accent)]/20">
            <Shield size={28} className="text-[var(--color-accent)]" />
          </div>
        </div>

        <h2 className="text-2xl font-bold text-center mb-1">
          Sovereign AI Hub
        </h2>
        <p className="text-xs text-[var(--color-text-muted)] text-center mb-6">
          Secure, air-gapped AI platform
        </p>

        <div className="flex mb-6 border border-[var(--color-border)] rounded-lg overflow-hidden">
          <button
            onClick={() => setMode("login")}
            className={`flex-1 py-2 text-sm font-medium transition-colors ${
              mode === "login"
                ? "bg-[var(--color-accent)] text-white"
                : "bg-[var(--color-surface)] text-[var(--color-text-muted)]"
            }`}
          >
            Login
          </button>
          <button
            onClick={() => setMode("register")}
            className={`flex-1 py-2 text-sm font-medium transition-colors ${
              mode === "register"
                ? "bg-[var(--color-accent)] text-white"
                : "bg-[var(--color-surface)] text-[var(--color-text-muted)]"
            }`}
          >
            Register
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === "register" && (
            <input
              type="text"
              placeholder="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-[var(--color-accent)]"
            />
          )}
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-[var(--color-accent)]"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="w-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-[var(--color-accent)]"
          />

          {error && (
            <p className="text-xs text-[var(--color-danger)]">{error}</p>
          )}

          <button
            type="submit"
            className="w-full py-3 bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white rounded-lg text-sm font-medium transition-colors"
          >
            {mode === "login" ? "Sign In" : "Create Account"}
          </button>
        </form>

        <p className="text-[10px] text-[var(--color-text-muted)] text-center mt-4">
          All data is stored locally. No external services are contacted.
        </p>
      </div>
    </div>
  );
}
