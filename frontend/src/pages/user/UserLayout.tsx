import { Link, NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext";
import { BrandMark } from "../../components/BrandMark";
import { NavIcon } from "../../components/NavIcon";

const links = [
  { to: "/app", end: true, label: "Resumen", icon: "dashboard" as const },
  { to: "/app/trades", label: "Operaciones", icon: "trades" as const },
  { to: "/app/history", label: "Historial", icon: "history" as const },
  { to: "/app/controls", label: "Control", icon: "controls" as const },
  { to: "/app/settings", label: "Ajustes", icon: "settings" as const },
];

export function UserLayout() {
  const { logout } = useAuth();
  return (
    <div className="layout user-layout">
      <header className="mobile-header">
        <BrandMark />
        <div><strong>Control Plane</strong><span>Mi bot</span></div>
        <Link className="mobile-results" to="/results" aria-label="Ver resultados de todas las cuentas"><NavIcon name="trades" /></Link>
        <button className="icon-button" onClick={logout} aria-label="Cerrar sesión"><NavIcon name="logout" /></button>
      </header>
      <nav className="sidebar" aria-label="Navegación principal">
        <Link to="/app" className="brand"><BrandMark /><div><strong>Control Plane</strong><span>Mi bot</span></div></Link>
        <div className="nav-group">
          {links.map((link) => <NavLink key={link.to} to={link.to} end={link.end}><NavIcon name={link.icon} /><span>{link.label}</span></NavLink>)}
        </div>
        <div className="nav-group sidebar-results"><NavLink to="/results"><NavIcon name="trades" /><span>Resultados globales</span></NavLink></div>
        <div className="spacer" />
        <button className="secondary logout-button" onClick={logout}><NavIcon name="logout" />Cerrar sesión</button>
      </nav>
      <main className="content" id="main-content" tabIndex={-1}><Outlet /></main>
      <nav className="bottom-nav" aria-label="Navegación móvil">
        {links.map((link) => <NavLink key={link.to} to={link.to} end={link.end}><NavIcon name={link.icon} /><span>{link.label}</span></NavLink>)}
      </nav>
    </div>
  );
}
