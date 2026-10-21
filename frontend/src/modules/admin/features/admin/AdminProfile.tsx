import { useEffect, useState } from 'react';
import { Shield, UserCog, Bell, LayoutDashboard, Activity, KeyRound, Save } from 'lucide-react';
import { adminProfileApi } from '@/api';
import { Card } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';
import type { AdminProfileResponse } from '@/shared/types/api';

/**
 * The administrator's own profile.
 *
 * Not the student profile with a different heading: an operator has no roll
 * number, no branch and no elective list, and none of it belongs on their
 * screen. What is here is what an operator actually works with - how they are
 * addressed, how the console is set up for them, where their alerts go, and
 * what they have been doing. Nothing of anybody else's: the activity feed is
 * their own actions, and the admin's view of *other* people is a different
 * screen (User 360) on purpose.
 */

const SUBSECTIONS = [
  { value: '', label: 'No default (remember my last)' },
  { value: 'A_W_HEALTH', label: 'A/W Health & Performance' },
  { value: 'B_W_ACTIVITY', label: 'B/W User Activity' },
  { value: 'C_W_SECURITY', label: 'C/W Security' },
  { value: 'D_W_FEEDBACK', label: 'D/W Feedback' },
  { value: 'A_A_HEALTH', label: 'A/A Health & Performance' },
  { value: 'B_A_ACTIVITY', label: 'B/A User Activity' },
  { value: 'C_A_SECURITY', label: 'C/A Security' },
  { value: 'D_A_FEEDBACK', label: 'D/A Feedback' },
];

const CHANNELS = [
  { value: 'email', label: 'Email' },
  { value: 'telegram', label: 'Telegram' },
  { value: 'webhook', label: 'Webhook' },
];

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-slate-700">{label}</span>
      {hint && <span className="block text-xs text-slate-500">{hint}</span>}
      <div className="mt-1">{children}</div>
    </label>
  );
}

const input =
  'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-teal-500 focus:outline-none';

export default function AdminProfile({ onError }: { onError?: (m: string) => void }) {
  const [profile, setProfile] = useState<AdminProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await adminProfileApi.get();
      setProfile(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
      onError?.(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const set = <K extends keyof AdminProfileResponse>(key: K, value: AdminProfileResponse[K]) => {
    setProfile(prev => (prev ? { ...prev, [key]: value } : prev));
  };

  const toggle = (list: string[], value: string) =>
    list.includes(value) ? list.filter(item => item !== value) : [...list, value];

  const save = async () => {
    if (!profile) return;
    setSaving(true);
    setSaved(false);
    try {
      const updated = await adminProfileApi.update({
        display_name: profile.display_name,
        job_title: profile.job_title,
        team: profile.team,
        timezone: profile.timezone,
        locale: profile.locale,
        theme: profile.theme,
        density: profile.density,
        default_subsection: profile.default_subsection,
        default_window_days: profile.default_window_days,
        pinned_panels: profile.pinned_panels,
        notify_email: profile.notify_email,
        notify_channels: profile.notify_channels,
        quiet_hours: profile.quiet_hours,
        notes: profile.notes,
      });
      setProfile(updated);
      setError(null);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <p className="p-6 text-sm text-slate-500">Loading your profile…</p>;
  if (!profile) return <ErrorBanner message={error ?? 'Could not load the profile'} />;

  return (
    <div className="space-y-5 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-800">
            <UserCog className="h-5 w-5 text-teal-600" />
            Administrator profile
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Yours alone: how you are addressed, how your console is set up, where your alerts go,
            and what you have been doing. Nothing about anybody else appears here.
          </p>
        </div>
        <button
          onClick={save}
          disabled={saving}
          className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-60"
        >
          <Save className="h-4 w-4" />
          {saving ? 'Saving…' : 'Save profile'}
        </button>
      </div>

      {error && <ErrorBanner message={error} />}
      {saved && !error && (
        <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          Saved. This profile is yours - nobody else can read or change it.
        </p>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <div className="mb-3 flex items-center gap-2">
            <UserCog className="h-4 w-4 text-teal-600" />
            <h3 className="text-base font-semibold text-slate-800">Identity</h3>
          </div>

          <div className="space-y-3">
            <Field label="Display name">
              <input
                className={input}
                value={profile.display_name ?? ''}
                onChange={e => set('display_name', e.target.value)}
                placeholder={profile.email}
              />
            </Field>
            <Field label="Job title">
              <input
                className={input}
                value={profile.job_title ?? ''}
                onChange={e => set('job_title', e.target.value)}
                placeholder="Platform administrator"
              />
            </Field>
            <Field label="Team">
              <input
                className={input}
                value={profile.team ?? ''}
                onChange={e => set('team', e.target.value)}
                placeholder="Infrastructure"
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Timezone">
                <input
                  className={input}
                  value={profile.timezone}
                  onChange={e => set('timezone', e.target.value)}
                />
              </Field>
              <Field label="Locale">
                <input
                  className={input}
                  value={profile.locale}
                  onChange={e => set('locale', e.target.value)}
                />
              </Field>
            </div>
          </div>
        </Card>

        <Card>
          <div className="mb-3 flex items-center gap-2">
            <LayoutDashboard className="h-4 w-4 text-teal-600" />
            <h3 className="text-base font-semibold text-slate-800">Console</h3>
          </div>

          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Theme">
                <select
                  className={input}
                  value={profile.theme}
                  onChange={e => set('theme', e.target.value as AdminProfileResponse['theme'])}
                >
                  <option value="system">System</option>
                  <option value="light">Light</option>
                  <option value="dark">Dark</option>
                </select>
              </Field>
              <Field label="Density">
                <select
                  className={input}
                  value={profile.density}
                  onChange={e => set('density', e.target.value as AdminProfileResponse['density'])}
                >
                  <option value="comfortable">Comfortable</option>
                  <option value="compact">Compact</option>
                </select>
              </Field>
            </div>
            <Field
              label="Default monitoring subsection"
              hint="Where the console lands when you open it."
            >
              <select
                className={input}
                value={profile.default_subsection ?? ''}
                onChange={e => set('default_subsection', e.target.value || null)}
              >
                {SUBSECTIONS.map(option => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Default window (days)">
              <input
                type="number"
                min={1}
                max={90}
                className={input}
                value={profile.default_window_days}
                onChange={e => set('default_window_days', Number(e.target.value))}
              />
            </Field>
            <Field
              label="Pinned panels"
              hint="Comma separated. These stay at the top of your console."
            >
              <input
                className={input}
                value={profile.pinned_panels.join(', ')}
                onChange={e =>
                  set(
                    'pinned_panels',
                    e.target.value
                      .split(',')
                      .map(item => item.trim())
                      .filter(Boolean)
                  )
                }
                placeholder="health, security"
              />
            </Field>
          </div>
        </Card>

        <Card>
          <div className="mb-3 flex items-center gap-2">
            <Bell className="h-4 w-4 text-teal-600" />
            <h3 className="text-base font-semibold text-slate-800">Alerts</h3>
          </div>

          <div className="space-y-3">
            <Field label="Notification email" hint="Where your alerts go.">
              <input
                className={input}
                value={profile.notify_email ?? ''}
                onChange={e => set('notify_email', e.target.value)}
                placeholder={profile.email}
              />
            </Field>
            <Field label="Channels">
              <div className="flex flex-wrap gap-3">
                {CHANNELS.map(channel => (
                  <label key={channel.value} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={profile.notify_channels.includes(channel.value)}
                      onChange={() =>
                        set('notify_channels', toggle(profile.notify_channels, channel.value))
                      }
                    />
                    {channel.label}
                  </label>
                ))}
              </div>
            </Field>
            <Field label="Quiet hours" hint='JSON: {"start": "22:00", "end": "07:00"}'>
              <input
                className={input}
                value={JSON.stringify(profile.quiet_hours ?? {})}
                onChange={e => {
                  try {
                    set('quiet_hours', JSON.parse(e.target.value || '{}'));
                  } catch {
                    /* keep the last valid value while typing */
                  }
                }}
              />
            </Field>
          </div>
        </Card>

        <Card>
          <div className="mb-3 flex items-center gap-2">
            <Shield className="h-4 w-4 text-teal-600" />
            <h3 className="text-base font-semibold text-slate-800">Account</h3>
          </div>

          <dl className="space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Email</dt>
              <dd className="font-medium text-slate-800">{profile.email}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Role</dt>
              <dd className="font-medium text-slate-800 capitalize">{profile.role}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Passkey</dt>
              <dd className="font-medium text-slate-800">
                {profile.passkey_registered ? 'Registered' : 'Not registered'}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Your actions on record</dt>
              <dd className="font-medium text-slate-800">{profile.own_action_count}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Account created</dt>
              <dd className="font-medium text-slate-800">
                {profile.account_created_at
                  ? new Date(profile.account_created_at).toLocaleDateString()
                  : '—'}
              </dd>
            </div>
          </dl>
          <Field label="Private notes" hint="Only you can read these.">
            <textarea
              className={`${input} min-h-20`}
              value={profile.notes ?? ''}
              onChange={e => set('notes', e.target.value)}
              placeholder="What are you working on? Where do you want to be reminded?"
            />
          </Field>
        </Card>
      </div>

      <Card>
        <div className="mb-3 flex items-center gap-2">
          <Activity className="h-4 w-4 text-teal-600" />
          <h3 className="text-base font-semibold text-slate-800">Your recent activity</h3>
        </div>

        {profile.recent_actions.length === 0 ? (
          <p className="text-sm text-slate-500">
            Nothing on record yet. This feed shows your own actions - other operators' actions are
            not in it.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100 text-sm">
            {profile.recent_actions.map(item => (
              <li key={item.id} className="flex items-center justify-between gap-4 py-2">
                <span className="flex items-center gap-2 text-slate-700">
                  <KeyRound className="h-3.5 w-3.5 text-slate-400" />
                  {item.action}
                  {item.target_type && (
                    <span className="text-xs text-slate-400">
                      on {item.target_type}
                      {item.target_id ? ` #${item.target_id}` : ''}
                    </span>
                  )}
                </span>
                <span className="text-xs text-slate-400">
                  {item.at ? new Date(item.at).toLocaleString() : ''}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
