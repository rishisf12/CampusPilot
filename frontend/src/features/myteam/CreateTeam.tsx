/** Create-team form. Same field markup as CampusPilot's upload/filter rows. */
import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react';

import { hackathonsApi, teamsApi } from '../../api';
import { SKILL_OPTIONS } from '../../constants';
import { useProfile } from '../../hooks/useProfile';
import type { Hackathon } from '../../types/api';

interface TeamForm {
  name: string;
  description: string;
  tech_stack: string;
  wanted: string;
  max_members: number;
  request_to_join: boolean;
  hackathon_id: string;
}

const EMPTY: TeamForm = {
  name: '',
  description: '',
  tech_stack: '',
  wanted: '',
  max_members: 4,
  request_to_join: false,
  hackathon_id: '',
};

interface CreateTeamProps {
  onCreated: () => void | Promise<void>;
  onCancel: () => void;
}

export default function CreateTeam({ onCreated, onCancel }: CreateTeamProps) {
  const { branch: profileBranch } = useProfile();
  const [form, setForm] = useState<TeamForm>(EMPTY);
  const [hackathons, setHackathons] = useState<Hackathon[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    hackathonsApi
      .list()
      .then(data => setHackathons(data.hackathons || []))
      .catch(() => setHackathons([]));
  }, []);

  const set =
    (key: keyof TeamForm) =>
    (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      const target = event.target as HTMLInputElement;
      const value =
        target.type === 'checkbox' ? (target as HTMLInputElement).checked : target.value;
      setForm(prev => ({ ...prev, [key]: value }) as TeamForm);
    };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await teamsApi.create({
        name: form.name.trim(),
        description: form.description.trim(),
        tech_stack: form.tech_stack
          .split(',')
          .map(t => t.trim())
          .filter(Boolean),
        wanted: form.wanted
          .split(',')
          .map(t => t.trim())
          .filter(Boolean),
        max_members: Number(form.max_members),
        request_to_join: form.request_to_join,
        hackathon_id: form.hackathon_id ? Number(form.hackathon_id) : null,
      });
      await onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create team');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <h2 className="text-lg font-semibold text-gray-900">Create a team</h2>
      <p className="text-sm text-gray-600 mt-1">
        Your branch is{' '}
        <span className="font-medium text-gray-900">{profileBranch || 'not set'}</span> — taken from
        your profile. Members of the same branch get a match bonus.
      </p>

      <form onSubmit={submit} className="mt-4 space-y-4">
        <div>
          <label className="label" htmlFor="team-name">
            Team name
          </label>
          <input
            id="team-name"
            className="input-field"
            value={form.name}
            onChange={set('name')}
            placeholder="e.g. Campus Lost &amp; Found"
            required
            minLength={3}
          />
        </div>

        <div>
          <label className="label" htmlFor="team-desc">
            What are you building?
          </label>
          <textarea
            id="team-desc"
            className="input-field"
            rows={3}
            value={form.description}
            onChange={set('description')}
            placeholder="One or two lines so people know what they are joining."
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="team-stack">
              Tech stack
            </label>
            <input
              id="team-stack"
              className="input-field"
              value={form.tech_stack}
              onChange={set('tech_stack')}
              placeholder="react, python, sql"
            />
            <p className="text-xs text-gray-500 mt-1">Comma separated. Used for matching.</p>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label className="label" htmlFor="team-size">
              Max members
            </label>
            <input
              id="team-size"
              type="number"
              min={2}
              max={20}
              className="input-field"
              value={form.max_members}
              onChange={set('max_members')}
            />
          </div>
          <div>
            <label className="label" htmlFor="team-hackathon">
              Hackathon
            </label>
            <select
              id="team-hackathon"
              className="select-field"
              value={form.hackathon_id}
              onChange={set('hackathon_id')}
            >
              <option value="">None</option>
              {hackathons.map(h => (
                <option key={h.id} value={h.id}>
                  {h.title}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={form.request_to_join}
                onChange={set('request_to_join')}
                className="rounded border-gray-300"
              />
              Approve joins
            </label>
          </div>
        </div>

        <div>
          <label className="label" htmlFor="team-wanted-gaps">
            Skills you are missing
          </label>
          <input
            id="team-wanted-gaps"
            className="input-field"
            value={form.wanted}
            onChange={set('wanted')}
            placeholder="nodejs, docker"
          />
          <p className="text-xs text-gray-500 mt-1">
            This is the gap candidates are scored against. Without it, anyone who already knows your
            stack scores higher than someone who adds what you lack.
          </p>
        </div>

        {error && (
          <div className="rounded-lg bg-danger-50 border border-danger-200 px-4 py-3">
            <p className="text-sm text-danger-700">{error}</p>
          </div>
        )}

        <div className="flex items-center gap-2 pt-2 border-t border-gray-100">
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? 'Creating...' : 'Create team'}
          </button>
          <button type="button" className="btn-secondary" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

export { SKILL_OPTIONS };
