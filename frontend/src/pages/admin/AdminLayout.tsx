import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext";
import { NavIcon } from "../../components/NavIcon";

export function AdminLayout() {
  const { logout } = useAuth();
  return (
    <div className="layout">
      <header className="mobile-header">
        <div className="brand-mark">CP</div>
        <div><strong>Admin</strong><span>Control Plane</span></div>
        <button className="icon-button" onClick={logout} aria-label="Cerrar sesión"><NavIcon name="logout" /></button>
      </header>
      <nav className="sidebar">
        <div className="brand"><div className="brand-mark">CP</div><div><strong>Admin</strong><span>Control Plane</span></div></div>
        <div className="nav-group"><NavLink to="/admin" end><NavIcon name="users" /><span>Users</span></NavLink></div>
        <div className="spacer" />
        <button className="secondary logout-button" onClick={logout}><NavIcon name="logout" />Log out</button>
      </nav>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
