import { useEffect, useState } from 'react';
import { adminApi, AdminUser } from '@/api';
import ErrorBanner from '@shared/components/ErrorBanner';

export default function Users({ onError }: { onError?: (m: string) => void }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<{
    total: number;
    admins: number;
    students: number;
    verified: number;
  } | null>(null);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [list, st] = await Promise.all([
        adminApi.users({
          search: search || undefined,
          role: roleFilter || undefined,
          page,
          size: 20,
        }),
        adminApi.stats(),
      ]);
      setUsers(list.users);
      setTotal(list.total);
      setStats(st);
      setError(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load users';
      setError(msg);
      onError?.(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, roleFilter]);

  const changeRole = async (u: AdminUser, next: 'admin' | 'student') => {
    if (u.role === next) return;
    setActing(u.id);
    try {
      const updated = await adminApi.setRole(u.id, next);
      setUsers(prev => prev.map(x => (x.id === u.id ? updated : x)));
      const st = await adminApi.stats();
      setStats(st);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Role change failed';
      setError(msg);
    } finally {
      setActing(null);
    }
  };

  if (loading)
    return <div className="card p-8 text-center text-sm text-gray-500">Loading users…</div>;

  return (
    <div className="space-y-4">
      <div className="card p-6">
        <h2 className="text-lg font-semibold text-gray-900">Users</h2>
        <p className="text-sm text-gray-600 mt-1">
          {total} accounts
          {stats
            ? ` · ${stats.admins} admins · ${stats.students} students · ${stats.verified} verified`
            : ''}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') {
                setPage(1);
                load();
              }
            }}
            placeholder="Search email, username, name, roll number…"
            className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm w-64"
          />
          <select
            value={roleFilter}
            onChange={e => {
              setRoleFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm"
          >
            <option value="">All roles</option>
            <option value="admin">Admin</option>
            <option value="student">Student</option>
          </select>
          <button
            type="button"
            onClick={() => {
              setPage(1);
              load();
            }}
            className="btn-primary text-sm"
          >
            Search
          </button>
        </div>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {users.map(u => (
        <div key={u.id} className="card p-4 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">
              {u.username} <span className="text-gray-400">· {u.email}</span>
            </p>
            <p className="text-xs text-gray-500">
              {u.full_name || '—'} {u.roll_number ? `· ${u.roll_number}` : ''} · {u.role}{' '}
              {u.is_email_verified ? '· verified' : '· unverified'}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {u.role === 'admin' ? (
              <button
                type="button"
                disabled={acting === u.id}
                onClick={() => changeRole(u, 'student')}
                className="btn-ghost text-sm disabled:opacity-60"
              >
                Demote
              </button>
            ) : (
              <button
                type="button"
                disabled={acting === u.id}
                onClick={() => changeRole(u, 'admin')}
                className="btn-primary text-sm disabled:opacity-60"
              >
                Make admin
              </button>
            )}
          </div>
        </div>
      ))}

      {users.length === 0 && (
        <div className="card p-8 text-center text-sm text-gray-500">No users found.</div>
      )}

      <div className="flex items-center justify-between text-sm text-gray-600">
        <span>
          Page {page} · {total} total
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage(p => Math.max(1, p - 1))}
            className="btn-ghost text-sm disabled:opacity-50"
          >
            Prev
          </button>
          <button
            type="button"
            disabled={users.length < 20}
            onClick={() => setPage(p => p + 1)}
            className="btn-ghost text-sm disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
