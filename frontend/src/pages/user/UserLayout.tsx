import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext";
import { NavIcon } from "../../components/NavIcon";

const links = [
  { to: "/app", end: true, label: "Dashboard", short: "Inicio", icon: "dashboard" as const },
  { to: "/app/trades", label: "Trades", short: "Trades", icon: "trades" as const },
  { to: "/app/history", label: "Historial", short: "Historial", icon: "history" as const },
  { to: "/app/controls", label: "Controls", short: "Control", icon: "controls" as const },
  { to: "/app/settings", label: "Settings", short: "Ajustes", icon: "settings" as const },
];

export function UserLayout() {
  const { logout } = useAuth();
  return (
    <div className="layout user-layout">
      <header className="mobile-header">
        <div className="brand-mark">FT</div>
        <div><strong>My Bot</strong><span>Control Plane</span></div>
        <button className="icon-button" onClick={logout} aria-label="Cerrar sesión"><NavIcon name="logout" /></button>
      </header>
      <nav className="sidebar">
        <div className="brand"><div className="brand-mark">FT</div><div><strong>My Bot</strong><span>Control Plane</span></div></div>
        <div className="nav-group">
          {links.map((link) => <NavLink key={link.to} to={link.to} end={link.end}><NavIcon name={link.icon} /><span>{link.label}</span></NavLink>)}
        </div>
        <div className="spacer" />
        <button className="secondary logout-button" onClick={logout}><NavIcon name="logout" />Log out</button>
      </nav>
      <main className="content">
        <Outlet />
      </main>
      <nav className="bottom-nav" aria-label="Navegación principal">
        {links.map((link) => <NavLink key={link.to} to={link.to} end={link.end}><NavIcon name={link.icon} /><span>{link.short}</span></NavLink>)}
      </nav>
    </div>
  );
}
