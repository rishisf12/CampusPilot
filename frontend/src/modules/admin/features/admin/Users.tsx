import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Search } from 'lucide-react';
import { adminApi, AdminUser } from '@/api';
import { Badge, Button, Card, Input, Select, Table } from '@/components/ui';
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
    return (
      <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
        Loading users…
      </Card>
    );

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
          Users
        </h2>
        <p className="text-sm mt-1" style={{ color: 'var(--cp-muted)' }}>
          {total} accounts
          {stats
            ? ` · ${stats.admins} admins · ${stats.students} students · ${stats.verified} verified`
            : ''}
        </p>
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <div className="w-64 max-w-full">
            <span className="label">Search</span>
            <Input
              id="admin-user-search"
              value={search}
              onChange={e => setSearch(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') {
                  setPage(1);
                  load();
                }
              }}
              placeholder="Search email, username, name, roll number…"
            />
          </div>
          <div>
            <span className="label">Role</span>
            <Select
              id="admin-role-filter"
              value={roleFilter}
              onChange={e => {
                setRoleFilter(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All roles</option>
              <option value="admin">Admin</option>
              <option value="student">Student</option>
            </Select>
          </div>
          <Button
            type="button"
            variant="primary"
            size="sm"
            icon={<Search size={16} strokeWidth={2} aria-hidden />}
            onClick={() => {
              setPage(1);
              load();
            }}
          >
            Search
          </Button>
        </div>
      </Card>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {users.length === 0 ? (
        <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
          No users found.
        </Card>
      ) : (
        <div aria-live="polite">
          <Table
            head={['User', 'Role', 'Status', 'Actions']}
            rows={users.map(u => [
              <span key="u">
                <span
                  className="block text-sm font-medium truncate"
                  style={{ color: 'var(--cp-text)' }}
                >
                  {u.username} <span style={{ color: 'var(--cp-muted)' }}>· {u.email}</span>
                </span>
                <span className="block text-xs" style={{ color: 'var(--cp-muted)' }}>
                  {u.full_name || '—'} {u.roll_number ? `· ${u.roll_number}` : ''}
                </span>
              </span>,
              <Badge key="r" tone={u.role === 'admin' ? 'primary' : 'neutral'}>
                {u.role}
              </Badge>,
              <Badge key="s" tone={u.is_email_verified ? 'success' : 'warning'}>
                {u.is_email_verified ? 'verified' : 'unverified'}
              </Badge>,
              u.role === 'admin' ? (
                <Button
                  key="a"
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={acting === u.id}
                  onClick={() => changeRole(u, 'student')}
                >
                  Demote
                </Button>
              ) : (
                <Button
                  key="a"
                  type="button"
                  variant="primary"
                  size="sm"
                  disabled={acting === u.id}
                  onClick={() => changeRole(u, 'admin')}
                >
                  Make admin
                </Button>
              ),
            ])}
          />
        </div>
      )}

      <div
        className="flex items-center justify-between text-sm"
        style={{ color: 'var(--cp-muted)' }}
      >
        <span aria-live="polite">
          Page {page} · {total} total
        </span>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            icon={<ChevronLeft size={16} strokeWidth={2} aria-hidden />}
            disabled={page <= 1}
            onClick={() => setPage(p => Math.max(1, p - 1))}
          >
            Prev
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            iconPosition="right"
            icon={<ChevronRight size={16} strokeWidth={2} aria-hidden />}
            disabled={users.length < 20}
            onClick={() => setPage(p => p + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
