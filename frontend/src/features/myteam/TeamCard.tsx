/** One team in the grid. Layout and status pill follow the attendance card. */
import MatchScore from './MatchScore';
import type { Team } from '../../types/api';

/** Team as the discover/feed endpoints return it, with display fields added. */
export interface TeamWithMeta extends Team {
  is_owner?: boolean;
  role?: string;
  match?: MatchInfo | null;
}

export interface MatchInfo {
  score?: number | null;
  fill_pct?: number | null;
  overlap_pct?: number | null;
  same_branch?: boolean;
  branch_bonus?: number;
  reason?: string;
}

export interface TeamStatus {
  label: string;
  tone: 'success' | 'warning' | 'danger';
}

const PILL: Record<'success' | 'warning' | 'danger', string> = {
  success: 'bg-success-50 text-success-700',
  warning: 'bg-warning-50 text-warning-700',
  danger: 'bg-danger-50 text-danger-700',
};

/** "closes in 12 days" / "closes tomorrow" / "no deadline" */
function deadlineLabel(endsAt: string | undefined | null): string | null {
  if (!endsAt) return null;
  const then = new Date(endsAt);
  if (Number.isNaN(then.getTime())) return null;
  const days = Math.ceil((then.getTime() - Date.now()) / 86400000);
  if (days < 0) return 'closed';
  if (days === 0) return 'closes today';
  if (days === 1) return 'closes tomorrow';
  if (days <= 30) return `closes in ${days} days`;
  return `closes in ${Math.round(days / 7)} weeks`;
}

interface TeamCardProps {
  team: TeamWithMeta;
  match?: MatchInfo | null;
  status: TeamStatus;
  onView: (team: TeamWithMeta) => void;
  onJoin: (team: TeamWithMeta) => void;
  actionLabel?: string;
  busy?: boolean;
}

export default function TeamCard({
  team,
  match,
  status,
  onView,
  onJoin,
  actionLabel = 'Join',
  busy = false,
}: TeamCardProps) {
  const deadline = deadlineLabel(team.hackathon?.ends_at);

  return (
    <div className="card flex flex-col">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-base font-semibold text-gray-900">{team.name}</h3>
        <span
          className={`shrink-0 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${PILL[status.tone]}`}
        >
          {status.label}
        </span>
      </div>

      {team.hackathon && (
        <p className="text-xs text-gray-500 mt-1">
          <span className="text-gray-700">{team.hackathon.title}</span>
          {deadline && <span> · {deadline}</span>}
        </p>
      )}

      {team.description && (
        <p className="text-sm text-gray-600 mt-1 line-clamp-2">{team.description}</p>
      )}

      {match && (
        <MatchScore
          score={match.score}
          fillPct={match.fill_pct}
          overlapPct={match.overlap_pct}
          sameBranch={match.same_branch}
          branchBonus={match.branch_bonus}
        />
      )}

      {match?.reason && <p className="text-xs text-gray-600 mt-2">{match.reason}</p>}

      <p className="text-xs text-gray-500 mt-3">
        {team.owner_branch ? `${team.owner_branch} · ` : ''}
        {team.members_count} of {team.max_members} members
        {(team.spots_left ?? 0) > 0 &&
          ` · ${team.spots_left} spot${team.spots_left === 1 ? '' : 's'} left`}
      </p>

      {match && team.tech_stack.length > 0 && (
        <p className="text-xs text-gray-500 mt-1">Stack: {team.tech_stack.join(', ')}</p>
      )}

      <div className="mt-auto pt-4 flex items-center gap-2">
        <button type="button" className="btn-primary" onClick={() => onView(team)}>
          View Details
        </button>
        {!team.is_owner && (
          <button
            type="button"
            className="btn-secondary"
            onClick={() => onJoin(team)}
            disabled={busy}
          >
            {actionLabel}
          </button>
        )}
        {team.is_owner && (
          <span className="px-2 py-0.5 rounded-full bg-primary-50 text-primary-700 text-[10px] font-semibold uppercase">
            Your team
          </span>
        )}
      </div>
    </div>
  );
}
