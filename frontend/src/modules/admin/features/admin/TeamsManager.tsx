import { useEffect, useState } from 'react';
import { adminApi } from '@/api';
import ErrorBanner from '@shared/components/ErrorBanner';

interface AdminTeam {
  id: number;
  name: string;
  description: string;
  owner_id: number | null;
  members: number;
  max_members: number;
  is_open: boolean;
  hackathon_id: number | null;
}

export default function TeamsManager({ onError }: { onError?: (m: string) => void }) {
  const [teams, setTeams] = useState<AdminTeam[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await adminApi.teams({ search: search || undefined, page, size: 20 });
      setTeams(r.teams);
      setTotal(r.total);
      setError(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load teams';
      setError(msg);
      onError?.(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  const remove = async (t: AdminTeam) => {
    if (!confirm(`Delete team "${t.name}"? Members and join requests go with it.`)) return;
    setActing(t.id);
    try {
      await adminApi.deleteTeam(t.id);
      setTeams(prev => prev.filter(x => x.id !== t.id));
      setTotal(n => Math.max(0, n - 1));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    } finally {
      setActing(null);
    }
  };

  if (loading)
    return <div className="card p-8 text-center text-sm text-gray-500">Loading teams…</div>;

  return (
    <div className="space-y-4">
      <div className="card p-6">
        <h2 className="text-lg font-semibold text-gray-900">Teams</h2>
        <p className="text-sm text-gray-600 mt-1">
          {total} teams · delete is moderation-only, ownership stays with students.
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
            placeholder="Search name, description…"
            className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm w-64"
          />
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

      {teams.map(t => (
        <div key={t.id} className="card p-4 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">{t.name}</p>
            <p className="text-xs text-gray-500">
              {t.members}/{t.max_members} members · {t.is_open ? 'open' : 'closed'}
              {t.hackathon_id ? ` · hackathon #${t.hackathon_id}` : ''} · owner #{t.owner_id ?? '—'}
            </p>
          </div>
          <button
            type="button"
            disabled={acting === t.id}
            onClick={() => remove(t)}
            className="btn-ghost text-sm disabled:opacity-50"
          >
            Delete
          </button>
        </div>
      ))}

      {teams.length === 0 && (
        <div className="card p-8 text-center text-sm text-gray-500">No teams found.</div>
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
            disabled={teams.length < 20}
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
