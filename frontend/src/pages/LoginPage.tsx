import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { BrandMark } from "../components/BrandMark";

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
      setError("Usuario o contraseña incorrectos. Inténtalo de nuevo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-wrap" id="main-content" tabIndex={-1}>
      <form className="card login-card" onSubmit={onSubmit}>
        <div className="brand"><BrandMark /><div><strong>Control Plane</strong><span>Tu centro de trading</span></div></div>
        <h1>Bienvenido</h1>
        <p className="muted">Accede para gestionar tu bot. Los resultados son públicos.</p>
        <label htmlFor="identifier">Usuario o correo de administrador</label>
        <input id="identifier" name="username" autoComplete="username" value={identifier} onChange={(e) => setIdentifier(e.target.value)} required autoFocus />
        <label htmlFor="password">Contraseña</label>
        <input id="password" name="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        <div className="mt-16"><button type="submit" disabled={busy || !identifier || !password}>{busy ? "Entrando…" : "Entrar"}</button></div>
        {error && <div className="error" role="alert">{error}</div>}
        <Link className="login-results" to="/results">Ver resultados de las cuentas ↗</Link>
      </form>
    </main>
  );
}
