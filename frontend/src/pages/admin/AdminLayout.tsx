import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext";

export function AdminLayout() {
  const { logout } = useAuth();
  return (
    <div className="layout">
      <nav className="sidebar">
        <h1>Admin</h1>
        <NavLink to="/admin" end>
          Users
        </NavLink>
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
