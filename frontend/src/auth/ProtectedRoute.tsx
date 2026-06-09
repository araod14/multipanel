import { Navigate } from "react-router-dom";

import type { Kind } from "../api/tokenStore";
import { useAuth } from "./AuthContext";

// Guards a route subtree, optionally requiring a specific principal kind.
export function ProtectedRoute({
  require,
  children,
}: {
  require?: Kind;
  children: React.ReactNode;
}) {
  const { isAuthed, kind } = useAuth();
  if (!isAuthed) return <Navigate to="/login" replace />;
  if (require && kind !== require) {
    // Wrong role: send to the area matching the actual role.
    return <Navigate to={kind === "admin" ? "/admin" : "/app"} replace />;
  }
  return <>{children}</>;
}
