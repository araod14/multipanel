import { Link, NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext";
import { BrandMark } from "../../components/BrandMark";
import { NavIcon } from "../../components/NavIcon";

export function AdminLayout() {
  const { logout } = useAuth();
  return (
    <div className="layout admin-layout">
      <header className="mobile-header">
        <BrandMark /><div><strong>Control Plane</strong><span>Administración</span></div>
        <button className="icon-button" onClick={logout} aria-label="Cerrar sesión"><NavIcon name="logout" /></button>
      </header>
      <nav className="sidebar" aria-label="Navegación principal">
        <Link to="/admin" className="brand"><BrandMark /><div><strong>Control Plane</strong><span>Administración</span></div></Link>
        <div className="nav-group"><NavLink to="/admin"><NavIcon name="users" /><span>Usuarios</span></NavLink><NavLink to="/results"><NavIcon name="trades" /><span>Resultados</span></NavLink></div>
        <div className="spacer" />
        <button className="secondary logout-button" onClick={logout}><NavIcon name="logout" />Cerrar sesión</button>
      </nav>
      <main className="content" id="main-content" tabIndex={-1}><Outlet /></main>
      <nav className="bottom-nav admin-bottom-nav" aria-label="Navegación móvil"><NavLink to="/admin"><NavIcon name="users" /><span>Usuarios</span></NavLink><NavLink to="/results"><NavIcon name="trades" /><span>Resultados</span></NavLink></nav>
    </div>
  );
}
