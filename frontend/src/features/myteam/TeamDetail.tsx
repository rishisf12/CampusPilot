/** Team detail: members grouped like the exam timetable's Day-1 / Day-2 sections. */
import { useEffect, useState } from 'react';

import { teamsApi } from '../../api';
import { ScoreBreakdown } from './MatchScore';
import type { TeamDetail, TeamMatchResult } from '../../types/api';

const PILL = {
  success: 'bg-success-50 text-success-700',
  warning: 'bg-warning-50 text-warning-700',
  danger: 'bg-danger-50 text-danger-700',
};

interface TeamDetailProps {
  teamId: number;
  match?: TeamMatchResult | null;
  onClose: () => void;
  onChanged?: () => void | Promise<void>;
}

export default function TeamDetailView({ teamId, match, onClose, onChanged }: TeamDetailProps) {
  const [team, setTeam] = useState<TeamDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      setLoading(true);
      const data = await teamsApi.get(teamId);
      setTeam(data);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load team');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [teamId]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError('');
    try {
      await fn();
      await load();
      if (onChanged) await onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Action failed');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-10 w-10 border-4 border-primary-500 border-t-transparent" />
      </div>
    );
  }

  if (!team) {
    return (
      <div className="card text-center py-10">
        <h3 className="text-lg font-semibold text-gray-900">Team not found</h3>
        {error && <p className="text-sm text-danger-600 mt-1">{error}</p>}
        <button type="button" className="btn-secondary mt-4" onClick={onClose}>
          Back
        </button>
      </div>
    );
  }

  const full = team.members_count >= team.max_members || !team.is_open;

  return (
    <div>
      <button type="button" className="btn-ghost mb-4" onClick={onClose}>
        Back to Discover
      </button>

      {error && (
        <div className="rounded-lg bg-danger-50 border border-danger-200 px-4 py-3 mb-4">
          <p className="text-sm text-danger-700">{error}</p>
        </div>
      )}

      <div className="card">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="text-xl font-bold text-gray-900">{team.name}</h2>
            <p className="text-sm text-gray-600 mt-1">{team.description}</p>
            <div className="flex flex-wrap gap-2 mt-3">
              <span
                className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                  full ? PILL.danger : PILL.success
                }`}
              >
                {full ? 'FULL' : 'OPEN'}
              </span>
              {team.request_to_join && (
                <span
                  className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${PILL.warning}`}
                >
                  APPROVAL REQUIRED
                </span>
              )}
              {team.tech_stack.map(tag => (
                <span
                  key={tag}
                  className="px-2 py-0.5 rounded-full bg-gray-100 text-gray-700 text-xs font-medium"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>

          <div className="flex flex-col items-end gap-2 shrink-0">
            {match && (
              <>
                <div className="w-56">
                  <ScoreBreakdown fillPct={match.fill_pct} overlapPct={match.overlap_pct} />
                </div>
                {match.team_gap.length > 0 && (
                  <div className="w-56 text-right">
                    <p className="text-[11px] text-gray-400">Their gap</p>
                    <p className="text-xs text-gray-600">{match.team_gap.join(', ')}</p>
                  </div>
                )}
                {match.reason && (
                  <p className="w-56 text-xs text-gray-600 text-right">{match.reason}</p>
                )}
              </>
            )}
            {!team.is_owner && (
              <button
                type="button"
                className="btn-primary"
                disabled={full || busy}
                onClick={() => act(() => teamsApi.join(team.id))}
              >
                {full ? 'Team Full' : 'Join team'}
              </button>
            )}
            {team.is_owner && (
              <button
                type="button"
                className="btn-danger"
                disabled={busy}
                onClick={() => act(() => teamsApi.remove(team.id))}
              >
                Delete team
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="card mt-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-gray-900">Members ({team.members.length})</h3>
          <button type="button" className="btn-ghost" onClick={load}>
            Refresh
          </button>
        </div>

        <div className="mt-4 space-y-2">
          {team.members.map((member, index) => (
            <div key={member.id}>
              {index > 0 && <div className="border-t border-gray-100 my-2" />}
              <div className="flex items-center justify-between gap-3 py-1">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900">
                    {member.full_name || member.username}
                    {member.is_admin && (
                      <span
                        className={`ml-2 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${PILL.warning}`}
                      >
                        Admin
                      </span>
                    )}
                  </p>
                  <p className="text-xs text-gray-500">
                    {member.branch ? `${member.branch} · ` : ''}@{member.username}
                  </p>
                </div>
                {member.skills.length > 0 && (
                  <div className="flex flex-wrap gap-1 justify-end">
                    {member.skills.map(skill => (
                      <span
                        key={skill}
                        className="px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 text-[10px] font-medium"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
