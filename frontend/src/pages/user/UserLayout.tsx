import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext";

export function UserLayout() {
  const { logout } = useAuth();
  return (
    <div className="layout">
      <nav className="sidebar">
        <h1>My Bot</h1>
        <NavLink to="/app" end>
          Dashboard
        </NavLink>
        <NavLink to="/app/trades">Trades</NavLink>
        <NavLink to="/app/controls">Controls</NavLink>
        <div className="spacer" />
        <button className="secondary" onClick={logout}>
          Log out
        </button>
      </nav>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
