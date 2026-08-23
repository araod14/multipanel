import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { adminApi } from "../../api/admin";

export function UsersPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { data: users, isLoading } = useQuery({
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
    onError: () => setError("Could not create user (duplicate username/email?)"),
  });

  const deleteUser = useMutation({
    mutationFn: (id: number) => adminApi.deleteUser(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  return (
    <>
      <div className="card">
        <h2>Create user</h2>
        <div className="form-grid create-user-form">
          <div className="field">
            <label>Username</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div className="field">
            <label>Email</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <label>Password</label>
            <input
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
              Create
            </button>
          </div>
        </div>
        {error && <div className="error">{error}</div>}
      </div>

      <div className="card">
        <h2>Users</h2>
        {isLoading ? (
          <p className="muted">Loading…</p>
        ) : (
          <table className="responsive-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Username</th>
                <th>Email</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users?.map((u) => (
                <tr key={u.id}>
                  <td data-label="ID">{u.id}</td>
                  <td data-label="Usuario" className="table-primary">{u.username}</td>
                  <td data-label="Email">{u.email}</td>
                  <td data-label="Estado">{u.status}</td>
                  <td data-label="Acciones" className="table-actions">
                    <div className="row">
                      <button className="secondary" onClick={() => navigate(`/admin/users/${u.id}`)}>
                        Manage
                      </button>
                      <button
                        className="danger"
                        onClick={() => {
                          if (confirm(`Delete user ${u.username} and its bot?`))
                            deleteUser.mutate(u.id);
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {users?.length === 0 && (
                <tr>
                  <td colSpan={5} className="muted">
                    No users yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
