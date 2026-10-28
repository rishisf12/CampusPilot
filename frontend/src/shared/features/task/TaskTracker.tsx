import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { AlarmClock, BellRing, Check, ListTodo, Pencil, Plus, X } from 'lucide-react';
import { taskApi } from '../../../api';
import type { TaskItem } from '../../types/api';

/** A task stays editable/completable for this long after creation. */
const TWENTY_FOUR_HOURS_MS = 24 * 60 * 60 * 1000;
/** How often the alarm watcher looks for due reminders. */
const WATCH_INTERVAL_MS = 15_000;

/** Local "now", corrected against the server clock read at list time. */
function useServerSkew() {
  const skewRef = useRef(0);
  const setFrom = useCallback((serverNowIso: string) => {
    const server = new Date(serverNowIso).getTime();
    if (Number.isFinite(server)) skewRef.current = server - Date.now();
  }, []);
  const now = useCallback(() => Date.now() + skewRef.current, []);
  return { setFrom, now };
}

/** Formats a Date for a datetime-local input, in local time. */
function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Short two-beep chime for a due alarm. Fails silently if audio is blocked. */
function beep() {
  try {
    const Ctx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    [0, 0.35].forEach(offset => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'sine';
      osc.frequency.value = 880;
      const t0 = ctx.currentTime + offset;
      gain.gain.setValueAtTime(0.0001, t0);
      gain.gain.exponentialRampToValueAtTime(0.2, t0 + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.28);
      osc.start(t0);
      osc.stop(t0 + 0.3);
    });
  } catch {
    // Autoplay policy or unsupported API: the visual toast still shows.
  }
}

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString([], {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** "23h 12m left" style countdown between the (skew-corrected) now and a stamp. */
function countdown(ms: number): string {
  if (ms <= 0) return 'expired';
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  if (h > 0) return `${h}h ${m}m left`;
  return `${m}m left`;
}

const BADGE: Record<TaskItem['status'], { label: string; bg: string; fg: string }> = {
  active: { label: 'Active', bg: 'rgba(13,148,136,.12)', fg: 'var(--cp-primary)' },
  completed: { label: 'Completed', bg: 'rgba(34,197,94,.14)', fg: '#15803d' },
  expired: { label: 'Expired', bg: 'rgba(239,68,68,.12)', fg: '#b91c1c' },
};

/**
 * Task - the 24-hour tracker.
 *
 * Created tasks stack newest-first. For 24 hours a task can be edited and
 * marked complete; after that it shows Expired and can no longer change, and
 * the server deletes it 48 hours after creation. The optional alarm fires an
 * in-app chime + banner the moment its time arrives, and can only be set
 * inside the upcoming 24 hours.
 */
export default function TaskTracker() {
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [remind, setRemind] = useState('');
  const [saving, setSaving] = useState(false);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editRemind, setEditRemind] = useState('');

  const [alarmToast, setAlarmToast] = useState<string | null>(null);
  const [, setTick] = useState(0);
  const firedRef = useRef<Set<number>>(new Set());
  const { setFrom, now } = useServerSkew();

  const load = useCallback(async () => {
    try {
      const res = await taskApi.list();
      setTasks(res.tasks);
      setFrom(res.server_now);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load tasks');
    } finally {
      setLoading(false);
    }
  }, [setFrom]);

  useEffect(() => {
    load();
  }, [load]);

  // Alarm watcher: chime + banner the moment an alarm is due, and refresh
  // the countdowns while it runs.
  useEffect(() => {
    const check = () => {
      const t = now();
      for (const task of tasks) {
        if (!task.remind_at || task.status !== 'active') continue;
        if (firedRef.current.has(task.id)) continue;
        if (t >= new Date(task.remind_at).getTime()) {
          firedRef.current.add(task.id);
          setAlarmToast(task.title);
          beep();
          window.setTimeout(() => {
            setAlarmToast(current => (current === task.title ? null : current));
          }, 8000);
        }
      }
      setTick(x => x + 1);
    };
    check();
    const iv = window.setInterval(check, WATCH_INTERVAL_MS);
    return () => window.clearInterval(iv);
  }, [tasks, now]);

  const alarmWindow = (value: string): string | null => {
    if (!value) return null;
    const when = new Date(value).getTime();
    if (!Number.isFinite(when) || when <= now()) return 'Alarm time must be in the future';
    if (when > now() + TWENTY_FOUR_HOURS_MS) return 'Alarm time cannot be more than 24 hours ahead';
    return null;
  };

  const toIso = (value: string): string | null => (value ? new Date(value).toISOString() : null);

  const create = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const text = title.trim();
    if (!text || saving) return;
    const alarmProblem = alarmWindow(remind);
    if (alarmProblem) {
      setError(alarmProblem);
      return;
    }
    setSaving(true);
    try {
      const task = await taskApi.create({ title: text, remind_at: toIso(remind) });
      setTasks(prev => [task, ...prev]);
      setTitle('');
      setRemind('');
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the task');
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (task: TaskItem) => {
    setEditingId(task.id);
    setEditTitle(task.title);
    setEditRemind(task.remind_at ? toLocalInput(new Date(task.remind_at)) : '');
  };

  const saveEdit = async () => {
    if (editingId == null || saving) return;
    const text = editTitle.trim();
    if (!text) {
      setError('Task title cannot be empty');
      return;
    }
    const alarmProblem = alarmWindow(editRemind);
    if (alarmProblem) {
      setError(alarmProblem);
      return;
    }
    setSaving(true);
    try {
      const updated = await taskApi.edit(editingId, { title: text, remind_at: toIso(editRemind) });
      setTasks(prev => prev.map(t => (t.id === updated.id ? updated : t)));
      setEditingId(null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the task');
    } finally {
      setSaving(false);
    }
  };

  const complete = async (task: TaskItem) => {
    try {
      const updated = await taskApi.complete(task.id);
      setTasks(prev => prev.map(t => (t.id === updated.id ? updated : t)));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not complete the task');
    }
  };

  const nowMs = now();
  // The picker refuses past times and anything beyond the next 24 hours.
  const minWhen = toLocalInput(new Date(nowMs + 60_000));
  const maxWhen = toLocalInput(new Date(nowMs + TWENTY_FOUR_HOURS_MS));

  return (
    <section className="max-w-2xl mx-auto w-full px-1 py-4 space-y-4">
      <header>
        <h1
          className="text-xl font-semibold flex items-center gap-2"
          style={{ color: 'var(--cp-text)' }}
        >
          <ListTodo className="w-5 h-5" aria-hidden />
          Task
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--cp-muted)' }}>
          You have 24 hours to complete or edit a task; it disappears 48 hours after it was created.
        </p>
      </header>

      {alarmToast && (
        <div
          className="flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-medium"
          style={{
            background: 'var(--cp-surface)',
            color: 'var(--cp-primary)',
            boxShadow: 'var(--cp-clay)',
          }}
          role="alert"
        >
          <BellRing className="w-4 h-4 animate-pulse" aria-hidden />
          <span>Alarm — due now: “{alarmToast}”</span>
          <button
            type="button"
            onClick={() => setAlarmToast(null)}
            className="ml-auto"
            aria-label="Dismiss alarm"
          >
            <X className="w-4 h-4" aria-hidden />
          </button>
        </div>
      )}

      {/* Create: title + optional alarm, stacked below as a card */}
      <form
        onSubmit={create}
        className="rounded-xl p-3 space-y-2"
        style={{ background: 'var(--cp-surface)', boxShadow: 'var(--cp-clay)' }}
      >
        <div className="flex gap-2">
          <input
            type="text"
            value={title}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setTitle(e.target.value)}
            placeholder="What needs doing?"
            maxLength={200}
            className="flex-1 min-w-0 rounded-lg px-3 py-2 text-sm outline-none"
            style={{
              background: 'rgba(255,255,255,.08)',
              border: '1px solid rgba(163,177,198,.3)',
              color: 'var(--cp-text)',
            }}
          />
          <button
            type="submit"
            disabled={!title.trim() || saving}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
            style={{ background: 'var(--cp-primary)', color: '#fff' }}
          >
            <Plus className="w-4 h-4" aria-hidden />
            Add
          </button>
        </div>
        <div
          className="flex items-center gap-2 flex-wrap text-xs"
          style={{ color: 'var(--cp-muted)' }}
        >
          <AlarmClock className="w-4 h-4 shrink-0" aria-hidden />
          <label htmlFor="task-alarm">Remind me at (optional, within 24h):</label>
          <input
            id="task-alarm"
            type="datetime-local"
            value={remind}
            min={minWhen}
            max={maxWhen}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setRemind(e.target.value)}
            className="rounded-lg px-2 py-1 text-xs outline-none"
            style={{
              background: 'rgba(255,255,255,.08)',
              border: '1px solid rgba(163,177,198,.3)',
              color: 'var(--cp-text)',
              colorScheme: 'dark light',
            }}
          />
        </div>
      </form>

      {error && (
        <p className="text-sm px-1" style={{ color: '#b91c1c' }} role="alert">
          {error}
        </p>
      )}

      {loading ? (
        <p className="text-sm text-center py-8" style={{ color: 'var(--cp-muted)' }}>
          Loading tasks…
        </p>
      ) : tasks.length === 0 ? (
        <p className="text-sm text-center py-8" style={{ color: 'var(--cp-muted)' }}>
          No tasks yet — add one above.
        </p>
      ) : (
        <ul className="space-y-2">
          {tasks.map(task => {
            const badge = BADGE[task.status];
            const isActive = task.status === 'active';
            const editing = editingId === task.id;
            const left = task.expires_at ? new Date(task.expires_at).getTime() - nowMs : 0;
            return (
              <li
                key={task.id}
                className="rounded-xl p-3"
                style={{ background: 'var(--cp-surface)', boxShadow: 'var(--cp-clay)' }}
              >
                {editing ? (
                  <div className="space-y-2">
                    <input
                      type="text"
                      value={editTitle}
                      maxLength={200}
                      onChange={(e: ChangeEvent<HTMLInputElement>) => setEditTitle(e.target.value)}
                      className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                      style={{
                        background: 'rgba(255,255,255,.08)',
                        border: '1px solid rgba(163,177,198,.3)',
                        color: 'var(--cp-text)',
                      }}
                    />
                    <div
                      className="flex items-center gap-2 flex-wrap text-xs"
                      style={{ color: 'var(--cp-muted)' }}
                    >
                      <AlarmClock className="w-4 h-4 shrink-0" aria-hidden />
                      <input
                        type="datetime-local"
                        value={editRemind}
                        min={minWhen}
                        max={maxWhen}
                        onChange={(e: ChangeEvent<HTMLInputElement>) =>
                          setEditRemind(e.target.value)
                        }
                        className="rounded-lg px-2 py-1 text-xs outline-none"
                        style={{
                          background: 'rgba(255,255,255,.08)',
                          border: '1px solid rgba(163,177,198,.3)',
                          color: 'var(--cp-text)',
                          colorScheme: 'dark light',
                        }}
                      />
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={saveEdit}
                        disabled={saving}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium disabled:opacity-50"
                        style={{ background: 'var(--cp-primary)', color: '#fff' }}
                      >
                        <Check className="w-3.5 h-3.5" aria-hidden />
                        Save
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditingId(null)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium"
                        style={{
                          background: 'rgba(255,255,255,.06)',
                          border: '1px solid rgba(163,177,198,.3)',
                          color: 'var(--cp-text)',
                        }}
                      >
                        <X className="w-3.5 h-3.5" aria-hidden />
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start gap-2">
                    <div className="flex-1 min-w-0">
                      <p
                        className={`text-sm font-medium break-words ${task.status === 'completed' ? 'line-through opacity-60' : ''}`}
                        style={{ color: 'var(--cp-text)' }}
                      >
                        {task.title}
                      </p>
                      <div
                        className="flex items-center gap-2 flex-wrap mt-1 text-xs"
                        style={{ color: 'var(--cp-muted)' }}
                      >
                        <span
                          className="px-2 py-0.5 rounded-full font-medium"
                          style={{ background: badge.bg, color: badge.fg }}
                        >
                          {badge.label}
                        </span>
                        {isActive && task.expires_at && <span>{countdown(left)}</span>}
                        {task.remind_at && task.status !== 'completed' && (
                          <span className="inline-flex items-center gap-1">
                            <AlarmClock className="w-3.5 h-3.5" aria-hidden />
                            {fmtTime(task.remind_at)}
                          </span>
                        )}
                        <span>created {fmtTime(task.created_at)}</span>
                      </div>
                    </div>
                    {isActive && (
                      <div className="flex gap-1.5 shrink-0">
                        <button
                          type="button"
                          onClick={() => complete(task)}
                          title="Mark as complete"
                          aria-label={`Mark "${task.title}" complete`}
                          className="p-1.5 rounded-lg"
                          style={{ background: 'rgba(34,197,94,.14)', color: '#15803d' }}
                        >
                          <Check className="w-4 h-4" aria-hidden />
                        </button>
                        <button
                          type="button"
                          onClick={() => startEdit(task)}
                          title="Edit"
                          aria-label={`Edit "${task.title}"`}
                          className="p-1.5 rounded-lg"
                          style={{
                            background: 'rgba(255,255,255,.06)',
                            border: '1px solid rgba(163,177,198,.3)',
                            color: 'var(--cp-text)',
                          }}
                        >
                          <Pencil className="w-4 h-4" aria-hidden />
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
