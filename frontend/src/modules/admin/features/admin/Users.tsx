import { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Search, Settings2 } from 'lucide-react';
import { adminApi, AdminUser } from '@/api';
import { Badge, Button, Card, Input, Modal, Select, Table } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';
import {
  ADMIN_STUDENT_GROUPS,
  BATCHLESS_PROGRAMMES,
  BRANCH_OPTIONS,
  PROGRAMME_SEMESTERS,
  semesterLabel,
} from '@shared/constants';

/**
 * The admin's user list.
 *
 * The filters are the ones an administrator thinks in: who is this person -
 * an admin, a member of the faculty, a student (undergraduate or
 * postgraduate), a class representative - and then which programme, which
 * batch, which branch, which semester. Every one of them starts unset, so
 * the list opens as every account rather than as a narrow slice of it.
 *
 * The hierarchy is progressive: a level appears only when it can mean
 * something. A programme only makes sense once a level is chosen, a batch
 * year only once a programme is, and a doctoral student joins no batch at
 * all, so that filter steps aside for them.
 */

type Category = '' | 'admin' | 'faculty' | 'students' | 'cr';
type Level = '' | 'UG' | 'PG';

const CATEGORIES: { value: Category; label: string }[] = [
  { value: '', label: 'Everyone' },
  { value: 'admin', label: 'Admins' },
  { value: 'faculty', label: 'Faculty' },
  { value: 'students', label: 'Students' },
  { value: 'cr', label: 'Class representatives' },
];

const SEMESTERS = Array.from(new Set(Object.values(PROGRAMME_SEMESTERS).flat())).sort(
  (a, b) => a - b
);

export default function Users({ onError }: { onError?: (m: string) => void }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<{
    total: number;
    admins: number;
    students: number;
    verified: number;
    faculty?: number;
    class_representatives?: number;
  } | null>(null);
  const [batchYears, setBatchYears] = useState<number[]>([]);

  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<Category>('');
  const [level, setLevel] = useState<Level>('');
  const [programme, setProgramme] = useState('');
  const [batchYear, setBatchYear] = useState('');
  const [branch, setBranch] = useState('');
  const [semester, setSemester] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState<number | null>(null);

  // The account being described, if any.
  const [editing, setEditing] = useState<AdminUser | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [list, st, filters] = await Promise.all([
        adminApi.users({
          search: search || undefined,
          category: category || undefined,
          group: level || undefined,
          programme: programme || undefined,
          batch_year: batchYear ? Number(batchYear) : undefined,
          branch: branch || undefined,
          semester: semester ? Number(semester) : undefined,
          page,
          size: 20,
        }),
        adminApi.stats(),
        adminApi.userFilters().catch(() => null),
      ]);
      setUsers(list.users);
      setTotal(list.total);
      setStats(st);
      if (filters) setBatchYears(filters.batch_years);
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
  }, [page, category, level, programme, batchYear, branch, semester]);

  /**
   * The programmes the chosen level offers, and whether they have a batch.
   *
   * A level with nothing chosen offers every programme under it: choosing
   * "postgraduate" and then "MTech" is two decisions, not one.
   */
  const levelProgrammes = useMemo(() => {
    if (!level) return [];
    return ADMIN_STUDENT_GROUPS[level] ?? [];
  }, [level]);

  const programmeHasBatch = programme
    ? !BATCHLESS_PROGRAMMES.includes(programme as (typeof BATCHLESS_PROGRAMMES)[number])
    : true;

  /** The batch years on offer: the ones the accounts carry. */
  const batchOptions = useMemo(() => {
    const years = new Set(batchYears);
    if (batchYear) years.add(Number(batchYear));
    return Array.from(years).sort((a, b) => b - a);
  }, [batchYears, batchYear]);

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
            ? ` · ${stats.admins} admins · ${stats.students} students · ${stats.verified} verified${
                stats.faculty ? ` · ${stats.faculty} faculty` : ''
              }${
                stats.class_representatives
                  ? ` · ${stats.class_representatives} class representatives`
                  : ''
              }`
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
            <span className="label">Who</span>
            <Select
              id="admin-user-category"
              value={category}
              onChange={e => {
                setCategory(e.target.value as Category);
                setPage(1);
                // The levels below belong to a category: a faculty member has
                // no programme group, so carrying one over would filter on
                // something that does not apply.
                setLevel('');
                setProgramme('');
              }}
            >
              {CATEGORIES.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>

          {(category === 'students' || category === 'cr') && (
            <div>
              <span className="label">Level</span>
              <Select
                id="admin-user-level"
                value={level}
                onChange={e => {
                  setLevel(e.target.value as Level);
                  setPage(1);
                  setProgramme('');
                }}
              >
                <option value="">All levels</option>
                {Object.keys(ADMIN_STUDENT_GROUPS).map(key => (
                  <option key={key} value={key}>
                    {key === 'UG' ? 'Undergraduate' : 'Postgraduate'}
                  </option>
                ))}
              </Select>
            </div>
          )}

          {category === 'students' && level && (
            <div>
              <span className="label">Programme</span>
              <Select
                id="admin-user-programme"
                value={programme}
                onChange={e => {
                  setProgramme(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">All programmes</option>
                {levelProgrammes.map(name => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </Select>
            </div>
          )}

          {(category === 'cr' || (category === 'students' && programme)) && (
            <div>
              <span className="label">Batch year</span>
              <Select
                id="admin-user-batch"
                value={batchYear}
                onChange={e => {
                  setBatchYear(e.target.value);
                  setPage(1);
                }}
                disabled={!programmeHasBatch}
              >
                <option value="">All batches</option>
                {batchOptions.map(year => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </Select>
            </div>
          )}

          <div>
            <span className="label">Branch</span>
            <Select
              id="admin-user-branch"
              value={branch}
              onChange={e => {
                setBranch(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All branches</option>
              {BRANCH_OPTIONS.map(name => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </Select>
          </div>

          <div>
            <span className="label">Semester</span>
            <Select
              id="admin-user-semester"
              value={semester}
              onChange={e => {
                setSemester(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All semesters</option>
              {SEMESTERS.map(value => (
                <option key={value} value={value}>
                  {semesterLabel(value)}
                </option>
              ))}
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

        <p className="mt-2 text-xs" style={{ color: 'var(--cp-muted)' }}>
          Clubs are not available yet.
        </p>
      </Card>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {users.length === 0 ? (
        <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
          No users found.
        </Card>
      ) : (
        <div aria-live="polite">
          <Table
            head={['User', 'Role', 'Who', 'Status', 'Actions']}
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
              <span key="w" className="text-xs">
                {u.is_faculty ? (
                  <Badge tone="primary">faculty</Badge>
                ) : u.is_class_representative ? (
                  <Badge tone="info">CR</Badge>
                ) : u.programme ? (
                  <span style={{ color: 'var(--cp-muted)' }}>
                    {u.programme}
                    {u.batch_year ? ` · ${u.batch_year}` : ''}
                    {u.branch ? ` · ${u.branch}` : ''}
                    {u.semester ? ` · Sem ${u.semester}` : ''}
                  </span>
                ) : (
                  <span style={{ color: 'var(--cp-muted)' }}>—</span>
                )}
              </span>,
              <Badge key="s" tone={u.is_email_verified ? 'success' : 'warning'}>
                {u.is_email_verified ? 'verified' : 'unverified'}
              </Badge>,
              <span key="a" className="flex items-center gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  title="Describe this account: programme, batch, class, faculty, CR"
                  onClick={() => setEditing(u)}
                >
                  <Settings2 size={14} strokeWidth={2} aria-hidden />
                </Button>
                {u.role === 'admin' ? (
                  <Button
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
                    type="button"
                    variant="primary"
                    size="sm"
                    disabled={acting === u.id}
                    onClick={() => changeRole(u, 'admin')}
                  >
                    Make admin
                  </Button>
                )}
              </span>,
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

      {editing && (
        <DescribeAccount
          user={editing}
          onClose={() => setEditing(null)}
          onSaved={updated => {
            setUsers(prev => prev.map(x => (x.id === updated.id ? updated : x)));
            setEditing(null);
            load();
          }}
          onError={msg => {
            setError(msg);
            onError?.(msg);
          }}
        />
      )}
    </div>
  );
}

/**
 * The account's details, as the college records them.
 *
 * A student may set their own branch and electives; who represents a class
 * and who teaches here is the college's call, so the admin sets it here.
 */
function DescribeAccount({
  user,
  onClose,
  onSaved,
  onError,
}: {
  user: AdminUser;
  onClose: () => void;
  onSaved: (user: AdminUser) => void;
  onError: (message: string) => void;
}) {
  const [programme, setProgramme] = useState(user.programme || '');
  const [semester, setSemester] = useState(String(user.semester ?? ''));
  const [branch, setBranch] = useState(user.branch || '');
  const [batchYear, setBatchYear] = useState(String(user.batch_year ?? ''));
  const [isFaculty, setIsFaculty] = useState(Boolean(user.is_faculty));
  const [isCr, setIsCr] = useState(Boolean(user.is_class_representative));
  const [saving, setSaving] = useState(false);

  const semesters = programme
    ? PROGRAMME_SEMESTERS[programme as keyof typeof PROGRAMME_SEMESTERS] || []
    : SEMESTERS;
  const branches = programme
    ? (ADMIN_BRANCHES[programme as keyof typeof ADMIN_BRANCHES] ?? BRANCH_OPTIONS)
    : BRANCH_OPTIONS;

  const save = async () => {
    setSaving(true);
    try {
      const updated = await adminApi.updateUser(user.id, {
        programme: programme || undefined,
        semester: semester ? Number(semester) : undefined,
        branch: branch || undefined,
        batch_year: batchYear ? Number(batchYear) : undefined,
        is_faculty: isFaculty,
        is_class_representative: isCr,
      });
      onSaved(updated);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Could not save the account');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal title={`${user.username} — who they are`} onClose={onClose}>
      <div className="space-y-3">
        <div>
          <span className="label">Programme</span>
          <Select
            value={programme}
            onChange={e => {
              setProgramme(e.target.value);
              setSemester('');
            }}
          >
            <option value="">Not set</option>
            {Object.keys(PROGRAMME_SEMESTERS).map(name => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </Select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <span className="label">Semester</span>
            <Select value={semester} onChange={e => setSemester(e.target.value)}>
              <option value="">Not set</option>
              {semesters.map(value => (
                <option key={value} value={value}>
                  {semesterLabel(value)}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <span className="label">Batch year</span>
            <Input
              type="number"
              min={2000}
              max={2100}
              step={1}
              value={batchYear}
              onChange={e => setBatchYear(e.target.value)}
              placeholder="2024"
            />
          </div>
        </div>
        <div>
          <span className="label">Branch</span>
          <Select value={branch} onChange={e => setBranch(e.target.value)}>
            <option value="">Not set</option>
            {branches.map(name => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </Select>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={isFaculty}
            onChange={e => setIsFaculty(e.target.checked)}
          />
          Member of the faculty
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={isCr} onChange={e => setIsCr(e.target.checked)} />
          Class representative
        </label>
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="button" variant="primary" size="sm" disabled={saving} onClick={save}>
            {saving ? 'Saving…' : 'Save'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

/** Branches offered per programme, as the profile offers them. */
const ADMIN_BRANCHES: Record<string, readonly string[]> = {
  BTech: ['CSE A', 'CSE B', 'ECE', 'ME', 'SM'],
  BDes: ['DS'],
  MTech: ['PG'],
  MDes: ['MDes'],
  PhD: ['PG'],
};
