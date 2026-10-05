import { PageHeading } from "../../components/PageHeading";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { adminApi } from "../../api/admin";

export function UsersPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { data: users, isLoading, isError, refetch } = useQuery({
    queryKey: ["users"],
    queryFn: adminApi.listUsers,
  });

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const createUser = useMutation({
    mutationFn: () => adminApi.createUser({ username, email, password }),
    onSuccess: () => {
      setUsername("");
      setEmail("");
      setPassword("");
      setError(null);
      qc.invalidateQueries({ queryKey: ["users"] });
    },
    onError: () => setError("No se pudo crear el usuario. Revisa si el nombre o correo ya existe."),
  });

  const deleteUser = useMutation({
    mutationFn: (id: number) => adminApi.deleteUser(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  return (
    <>
      <PageHeading title="Usuarios" description="Gestiona las cuentas y sus bots de trading." />
      <div className="card">
        <h2>Crear usuario</h2>
        <div className="form-grid create-user-form">
          <div className="field">
            <label htmlFor="userspage-field-1">Usuario</label>
            <input id="userspage-field-1" value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="userspage-field-2">Correo</label>
            <input id="userspage-field-2" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="userspage-field-3">Contraseña</label>
            <input id="userspage-field-3"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <div className="field-action mt-12">
            <button
              onClick={() => createUser.mutate()}
              disabled={!username || !email || password.length < 8 || createUser.isPending}
            >
              Crear
            </button>
          </div>
        </div>
        {error && <div className="error">{error}</div>}
      </div>

      <div className="card">
        <h2>Usuarios</h2>
        {isLoading ? (
          <p className="muted">Cargando…</p>
        ) : isError ? (
          <div className="notice notice--error" role="alert"><p>No se pudieron cargar los usuarios.</p><button className="secondary" onClick={() => void refetch()}>Reintentar</button></div>
        ) : (
          <table className="responsive-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Usuario</th>
                <th>Correo</th>
                <th>Estado</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users?.map((u) => (
                <tr key={u.id}>
                  <td data-label="ID">{u.id}</td>
                  <td data-label="Usuario" className="table-primary">{u.username}</td>
                  <td data-label="Correo">{u.email}</td>
                  <td data-label="Estado"><span className={`badge ${u.status === "active" ? "running" : "stopped"}`}>{u.status === "active" ? "Activo" : "Suspendido"}</span></td>
                  <td data-label="Acciones" className="table-actions">
                    <div className="row">
                      <button className="secondary" onClick={() => navigate(`/admin/users/${u.id}`)}>
                        Gestionar
                      </button>
                      <button
                        className="danger"
                        disabled={deleteUser.isPending}
                        onClick={() => {
                          if (confirm(`¿Eliminar el usuario ${u.username} y su bot?`))
                            deleteUser.mutate(u.id);
                        }}
                      >
                        Eliminar
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {users?.length === 0 && (
                <tr>
                  <td colSpan={5} className="muted">
                    Todavía no hay usuarios.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
      {deleteUser.isError && <p className="error" role="alert">No se pudo eliminar el usuario.</p>}
    </>
  );
}
