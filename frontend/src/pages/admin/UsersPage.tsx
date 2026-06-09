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
        <div className="row">
          <div style={{ flex: 1 }}>
            <label>Username</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div style={{ flex: 1 }}>
            <label>Email</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div style={{ flex: 1 }}>
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <div style={{ alignSelf: "flex-end" }}>
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
          <table>
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
                  <td>{u.id}</td>
                  <td>{u.username}</td>
                  <td>{u.email}</td>
                  <td>{u.status}</td>
                  <td className="row" style={{ justifyContent: "flex-end" }}>
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
