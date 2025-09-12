import React, { useEffect, useState } from 'react';
import { addAllowedUserFn, listAllowedUsersFn, removeAllowedUserFn, setAllowedUserRoleFn } from '../../config/firebase';

type AllowedUser = {
  id: string;
  email: string;
  role: string;
};

export const AllowedUsersPanel: React.FC = () => {
  const [users, setUsers] = useState<AllowedUser[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [newEmail, setNewEmail] = useState<string>('');
  const [newRole, setNewRole] = useState<string>('recruiter');
  const [authorized, setAuthorized] = useState<boolean>(true);

  const loadUsers = async () => {
    setLoading(true);
    setError('');
    try {
      const resp: any = await listAllowedUsersFn({});
      setUsers((resp.data?.users || []) as AllowedUser[]);
      setAuthorized(true);
    } catch (e: any) {
      // Permission denied means caller is not admin; silently hide panel
      if (e?.message && String(e.message).toLowerCase().includes('permission')) {
        setAuthorized(false);
        setUsers([]);
      } else {
        setError('Failed to load allowed users');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const handleAdd = async () => {
    if (!newEmail) return;
    try {
      await addAllowedUserFn({ email: newEmail, role: newRole });
      setNewEmail('');
      await loadUsers();
    } catch {
      setError('Failed to add user');
    }
  };

  const handleRemove = async (email: string) => {
    try {
      await removeAllowedUserFn({ email });
      await loadUsers();
    } catch {
      setError('Failed to remove user');
    }
  };

  const handleSetRole = async (email: string, role: string) => {
    try {
      await setAllowedUserRoleFn({ email, role });
      await loadUsers();
    } catch {
      setError('Failed to update role');
    }
  };

  if (!authorized) return null;

  return (
    <div className="dashboard-section">
      <div className="section-header">
        <h2>Admin: Allowed Users</h2>
        <p>Manage who can access the application and their role</p>
      </div>

      {error && (
        <div className="error-container" style={{ marginBottom: 12 }}>
          <div className="error-icon">⚠️</div>
          <p>{error}</p>
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center' }}>
        <input
          type="email"
          placeholder="email@company.com"
          value={newEmail}
          onChange={(e) => setNewEmail(e.target.value)}
          style={{ flex: 1, padding: 8 }}
        />
        <select value={newRole} onChange={(e) => setNewRole(e.target.value)}>
          <option value="recruiter">recruiter</option>
          <option value="admin">admin</option>
        </select>
        <button className="btn btn-primary" onClick={handleAdd} disabled={loading}>
          Add
        </button>
      </div>

      {loading ? (
        <div className="loading-container"><div className="loading-spinner"></div><p>Loading allowed users...</p></div>
      ) : users.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📭</div>
          <h3>No allowed users</h3>
          <p>Add an email to grant access</p>
        </div>
      ) : (
        <div className="table-responsive">
          <table className="table">
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>Email</th>
                <th style={{ textAlign: 'left' }}>Role</th>
                <th style={{ textAlign: 'left' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.email}</td>
                  <td>
                    <select value={u.role} onChange={(e) => handleSetRole(u.email, e.target.value)}>
                      <option value="recruiter">recruiter</option>
                      <option value="admin">admin</option>
                    </select>
                  </td>
                  <td>
                    <button className="btn" onClick={() => handleRemove(u.email)} disabled={loading}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};


