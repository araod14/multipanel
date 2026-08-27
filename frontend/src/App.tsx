import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth/AuthContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { LoginPage } from "./pages/LoginPage";
import { ResultsPage } from "./pages/public/ResultsPage";
import { AdminLayout } from "./pages/admin/AdminLayout";
import { UsersPage } from "./pages/admin/UsersPage";
import { UserDetailPage } from "./pages/admin/UserDetailPage";
import { UserLayout } from "./pages/user/UserLayout";
import { DashboardPage } from "./pages/user/DashboardPage";
import { TradesPage } from "./pages/user/TradesPage";
import { HistoryPage } from "./pages/user/HistoryPage";
import { ControlsPage } from "./pages/user/ControlsPage";
import { SettingsPage } from "./pages/user/SettingsPage";

export function App() {
  const { isAuthed, kind } = useAuth();

  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthed ? <Navigate to={kind === "admin" ? "/admin" : "/app"} replace /> : <LoginPage />}
      />

      {/* Public: no ProtectedRoute, deliberately reachable without a session. */}
      <Route path="/results" element={<ResultsPage />} />

      <Route
        path="/admin"
        element={
          <ProtectedRoute require="admin">
            <AdminLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<UsersPage />} />
        <Route path="users/:userId" element={<UserDetailPage />} />
      </Route>

      <Route
        path="/app"
        element={
          <ProtectedRoute require="user">
            <UserLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="trades" element={<TradesPage />} />
        <Route path="history" element={<HistoryPage />} />
        <Route path="controls" element={<ControlsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>

      <Route path="*" element={<Navigate to={isAuthed ? (kind === "admin" ? "/admin" : "/app") : "/login"} replace />} />
    </Routes>
  );
}
