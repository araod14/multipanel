import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const kind = await login(identifier, password);
      navigate(kind === "admin" ? "/admin" : "/app", { replace: true });
    } catch {
      setError("Invalid credentials");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="card login-card" onSubmit={onSubmit}>
        <h2>Control Plane</h2>
        <p className="muted">Admin email or user username.</p>
        <label>Identifier</label>
        <input value={identifier} onChange={(e) => setIdentifier(e.target.value)} autoFocus />
        <label>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <div style={{ marginTop: 16 }}>
          <button type="submit" disabled={busy || !identifier || !password}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </div>
        {error && <div className="error">{error}</div>}
      </form>
    </div>
  );
}
