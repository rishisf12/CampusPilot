/**
 * Teams.
 *
 * Four sub-tabs (Discover / My Teams / Requests / Hackathons) over one page,
 * driven by `?tab=` in the URL so a reload returns to the same view - the same
 * approach CampusPilot's App.tsx uses for its own tabs.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { teamsApi, hackathonsApi } from '../../api';
import { BRANCH_OPTIONS, TEAM_TABS, teamStatus } from '../../constants';
import { useProfile } from '../../hooks/useProfile';
import CreateTeam from './CreateTeam';
import Hackathons from './Hackathons';
import TeamCard from './TeamCard';
import type { TeamWithMeta } from './TeamCard';
import TeamDetail from './TeamDetail';
import type { Hackathon, MyTeam, TeamJoinRequest, TeamMatchResult } from '../../types/api';

const SUB_TABS = TEAM_TABS;

function Stat({
  label,
  value,
  tone = 'primary',
  hint,
}: {
  label: string;
  value: string | number;
  tone?: 'success' | 'warning' | 'primary';
  hint?: string;
}) {
  const tones = {
    success: 'bg-success-50 text-success-700',
    warning: 'bg-warning-50 text-warning-700',
    primary: 'bg-primary-50 text-primary-700',
  };
  return (
    <div className="card py-4">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${tones[tone]}`}>{value}</p>
      {hint && <p className="text-xs text-gray-500 mt-0.5">{hint}</p>}
    </div>
  );
}

export default function Teams() {
  const { branch: profileBranch } = useProfile();
  const [subTab, setSubTab] = useState<string>(() => {
    const requested = new URLSearchParams(window.location.search).get('teamtab');
    return SUB_TABS.some(item => item.id === requested) ? (requested as string) : 'discover';
  });
  const [matches, setMatches] = useState<TeamMatchResult[]>([]);
  const [mine, setMine] = useState<MyTeam[]>([]);
  const [requests, setRequests] = useState<TeamJoinRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [search, setSearch] = useState('');
  const [branchFilter, setBranchFilter] = useState('');
  const [minScore, setMinScore] = useState('');
  const [hackathonFilter, setHackathonFilter] = useState(
    () => new URLSearchParams(window.location.search).get('event') || ''
  );
  const [recruitingOnly, setRecruitingOnly] = useState(false);
  const [hackathons, setHackathons] = useState<Hackathon[]>([]);
  const loadId = useRef(0);

  const selectSubTab = (id: string) => {
    setSubTab(id);
    setDetailId(null);
    setShowCreate(false);
    const url = new URL(window.location.href);
    url.searchParams.set('teamtab', id);
    window.history.replaceState({}, '', url);
  };

  // Filter-scoped load. Only the ranking depends on the hackathon and
  // recruiting filters, so changing a filter must not refetch my teams, my
  // join requests and the event list - that would be four requests to redraw
  // one list, and the jumpy `loading` flag would blank the whole page.
  const loadMatches = useCallback(async () => {
    // StrictMode mounts effects twice in development, so two loads can be in
    // flight at once. Only the newest one is allowed to write state, otherwise
    // the slower earlier response can overwrite fresher data.
    loadId.current += 1;
    const id = loadId.current;

    try {
      setLoading(true);
      const matchData = await teamsApi.matches({
        hackathon_id: hackathonFilter || undefined,
        recruiting_only: recruitingOnly || undefined,
      });
      if (id !== loadId.current) return;
      setMatches(matchData.matches || []);
      setError('');
    } catch (err) {
      if (id !== loadId.current) return;
      setError(err instanceof Error ? err.message : 'Failed to load teams');
    } finally {
      if (id === loadId.current) setLoading(false);
    }
  }, [hackathonFilter, recruitingOnly]);

  // Everything that does not change with the filters. Loaded once per mount.
  const loadContext = useCallback(async () => {
    try {
      const [mineData, requestData, eventData] = await Promise.all([
        teamsApi.mine(),
        teamsApi.requests(),
        hackathonsApi.list({ is_active: true }),
      ]);
      setMine(mineData.teams || []);
      setRequests(requestData.requests || []);
      setHackathons(eventData.hackathons || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load teams');
    }
  }, []);

  const load = useCallback(async () => {
    await Promise.all([loadMatches(), loadContext()]);
  }, [loadMatches, loadContext]);

  /**
   * Page-level Refresh.
   *
   * The Hackathons tab keeps its own loader, so bumping a key and remounting it
   * is what makes this one button refresh whichever tab is open. Reloading only
   * the team data would leave a stale event list behind a button labelled
   * Refresh, which is worse than having no button at all.
   */
  const [tabEpoch, setTabEpoch] = useState(0);
  const refreshAll = useCallback(() => {
    load();
    setTabEpoch(value => value + 1);
  }, [load]);

  useEffect(() => {
    loadMatches();
  }, [loadMatches]);

  useEffect(() => {
    loadContext();
  }, [loadContext]);

  // /teams/mine returns teams flattened, same shape as /teams and /teams/match,
  // with `is_owner` and `role` alongside the team fields.
  const myTeamIds = useMemo(() => new Set(mine.map(team => team.id)), [mine]);

  const visible = useMemo(() => {
    const term = search.trim().toLowerCase();
    return matches.filter(team => {
      if (term && !team.name.toLowerCase().includes(term)) return false;
      if (branchFilter && team.owner_branch !== branchFilter) return false;
      if (minScore !== '' && team.score < Number(minScore)) return false;
      return true;
    });
  }, [matches, search, branchFilter, minScore]);

  const averageScore = useMemo(() => {
    if (!matches.length) return 0;
    const total = matches.reduce((sum, team) => sum + team.score, 0);
    return Math.round((total / matches.length) * 10) / 10;
  }, [matches]);

  const join = async (team: TeamWithMeta) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const result = await teamsApi.join(team.id);
      setNotice(
        result.status === 'pending'
          ? 'Request sent. The team owner will review it.'
          : 'You joined the team.'
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to join team');
    } finally {
      setBusy(false);
    }
  };

  const respond = async (requestId: number, status: 'accepted' | 'rejected') => {
    setBusy(true);
    setError('');
    try {
      await teamsApi.respond(requestId, status);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to respond');
    } finally {
      setBusy(false);
    }
  };

  const leave = async (team: TeamWithMeta) => {
    setBusy(true);
    setError('');
    try {
      await teamsApi.leave(team.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to leave team');
    } finally {
      setBusy(false);
    }
  };

  const detailMatch = useMemo(
    () => matches.find(team => team.id === detailId) || null,
    [matches, detailId]
  );

  if (detailId) {
    return (
      <TeamDetail
        teamId={detailId}
        match={detailMatch}
        onClose={() => setDetailId(null)}
        onChanged={load}
      />
    );
  }

  if (showCreate) {
    return (
      <CreateTeam
        onCancel={() => setShowCreate(false)}
        onCreated={async () => {
          setShowCreate(false);
          setNotice('Team created.');
          await load();
        }}
      />
    );
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        {/* Labels stay intact (`whitespace-nowrap`) and the strip wraps onto a
            second row when it must. Letting a two-word label break mid-word
            makes the row unreadable; a visible horizontal scrollbar is worse. */}
        <div className="flex flex-wrap items-center gap-x-2 border-b border-gray-200">
          {SUB_TABS.map(tab => (
            <button
              key={tab.id}
              type="button"
              onClick={() => selectSubTab(tab.id)}
              aria-current={subTab === tab.id ? 'page' : undefined}
              className={`sub-tab whitespace-nowrap shrink-0 ${subTab === tab.id ? 'sub-tab-active' : 'sub-tab-idle'}`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <button type="button" className="btn-ghost" onClick={refreshAll}>
          Refresh
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-danger-50 border border-danger-200 px-4 py-3 mb-4">
          <p className="text-sm text-danger-700">{error}</p>
        </div>
      )}
      {notice && (
        <div className="rounded-lg bg-success-50 border border-success-200 px-4 py-3 mb-4">
          <p className="text-sm text-success-700">{notice}</p>
        </div>
      )}

      {subTab === 'discover' && (
        <>
          <div className="flex items-center gap-2 mb-4">
            <span className="px-2.5 py-1 rounded-full bg-primary-50 text-primary-700 text-xs font-medium">
              Synced with profile · {profileBranch || 'no branch set'}
            </span>
          </div>

          <div className="grid gap-4 sm:grid-cols-3 mb-4">
            <Stat label="Open teams" value={matches.filter(t => t.is_open).length} tone="success" />
            <Stat
              label="Avg match"
              value={`${averageScore}%`}
              tone="primary"
              hint="Across all teams"
            />
            <Stat label="Your teams" value={mine.length} tone="warning" />
          </div>

          <div className="card mb-4">
            <div className="flex flex-wrap items-end gap-3">
              <div className="w-full sm:w-56">
                <label className="label" htmlFor="team-hackathon-filter">
                  Hackathon
                </label>
                <select
                  id="team-hackathon-filter"
                  className="select-field"
                  value={hackathonFilter}
                  onChange={e => {
                    setHackathonFilter(e.target.value);
                    // Keep the URL in step so the filtered view survives a
                    // reload and can be shared.
                    const url = new URL(window.location.href);
                    if (e.target.value) url.searchParams.set('event', e.target.value);
                    else url.searchParams.delete('event');
                    window.history.replaceState({}, '', url);
                  }}
                >
                  <option value="">All hackathons</option>
                  {hackathons.map(event => (
                    <option key={event.id} value={event.id}>
                      {event.title}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex-1 min-w-[12rem]">
                <label className="label" htmlFor="team-search">
                  Search
                </label>
                <input
                  id="team-search"
                  className="input-field"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="Team name..."
                />
              </div>
              <div className="w-full sm:w-36">
                <label className="label" htmlFor="team-branch">
                  Branch
                </label>
                <select
                  id="team-branch"
                  className="select-field"
                  value={branchFilter}
                  onChange={e => setBranchFilter(e.target.value)}
                >
                  <option value="">All branches</option>
                  {BRANCH_OPTIONS.map(branch => (
                    <option key={branch} value={branch}>
                      {branch}
                    </option>
                  ))}
                </select>
              </div>
              <div className="w-full sm:w-28">
                <label className="label" htmlFor="team-minscore">
                  Min match
                </label>
                <select
                  id="team-minscore"
                  className="select-field"
                  value={minScore}
                  onChange={e => setMinScore(e.target.value)}
                >
                  <option value="">Any</option>
                  <option value="20">20%+</option>
                  <option value="40">40%+</option>
                  <option value="60">60%+</option>
                  <option value="80">80%+</option>
                </select>
              </div>
              <label className="flex items-center gap-2 text-sm text-gray-700 pb-2">
                <input
                  type="checkbox"
                  checked={recruitingOnly}
                  onChange={e => setRecruitingOnly(e.target.checked)}
                  className="rounded border-gray-300"
                />
                Still recruiting
              </label>
              <button type="button" className="btn-primary" onClick={() => setShowCreate(true)}>
                + Create Team
              </button>
            </div>
          </div>

          {loading ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-10 w-10 border-4 border-primary-500 border-t-transparent" />
            </div>
          ) : visible.length === 0 ? (
            <div className="card text-center py-10">
              <h3 className="text-base font-semibold text-gray-900">
                {matches.length === 0 ? 'No teams yet' : 'No teams match those filters'}
              </h3>
              <p className="text-sm text-gray-600 mt-1">
                {matches.length === 0
                  ? 'Be the first to create one.'
                  : 'Clear the filters to see everything.'}
              </p>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {visible.map(team => (
                <TeamCard
                  key={team.id}
                  team={{ ...team, is_owner: myTeamIds.has(team.id) }}
                  match={team}
                  status={teamStatus(team, false)}
                  onView={() => setDetailId(team.id)}
                  onJoin={join}
                  busy={busy}
                />
              ))}
            </div>
          )}
        </>
      )}

      {subTab === 'mine' && (
        <>
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-2xl font-bold text-gray-900">My Teams</h1>
            <button type="button" className="btn-primary" onClick={() => setShowCreate(true)}>
              + Create Team
            </button>
          </div>

          {mine.length === 0 ? (
            <div className="card text-center py-10">
              <h3 className="text-base font-semibold text-gray-900">You are not in a team yet</h3>
              <p className="text-sm text-gray-600 mt-1">Find one on the Discover tab.</p>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {mine.map(team => (
                <TeamCard
                  key={team.id}
                  team={team}
                  status={teamStatus(team, false)}
                  onView={() => setDetailId(team.id)}
                  onJoin={() => leave(team)}
                  actionLabel="Leave"
                  busy={busy}
                />
              ))}
            </div>
          )}
        </>
      )}

      {subTab === 'requests' && (
        <>
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-2xl font-bold text-gray-900">Join Requests</h1>
            <span className="px-2.5 py-1 rounded-full bg-warning-50 text-warning-700 text-xs font-medium">
              {requests.length} pending
            </span>
          </div>

          {requests.length === 0 ? (
            <div className="card text-center py-10">
              <h3 className="text-base font-semibold text-gray-900">No pending requests</h3>
              <p className="text-sm text-gray-600 mt-1">
                Requests to join teams you own will show up here.
              </p>
            </div>
          ) : (
            <div className="card">
              <div className="overflow-x-auto scrollbar-thin">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left">
                      <th className="pb-2 font-medium text-gray-500">APPLICANT</th>
                      <th className="pb-2 font-medium text-gray-500">BRANCH</th>
                      <th className="pb-2 font-medium text-gray-500">TEAM</th>
                      <th className="pb-2 font-medium text-gray-500">MESSAGE</th>
                      <th className="pb-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {requests.map(item => (
                      <tr key={item.id} className="border-t border-gray-100">
                        <td className="py-2.5 font-medium text-gray-900">
                          {item.user_name || 'Unknown'}
                        </td>
                        <td className="py-2.5 text-gray-600">{item.user_branch || '-'}</td>
                        <td className="py-2.5 text-gray-600">{item.team_name}</td>
                        <td className="py-2.5 text-gray-500 max-w-xs truncate">
                          {item.message || '-'}
                        </td>
                        <td className="py-2.5">
                          <div className="flex items-center gap-2 justify-end">
                            <button
                              type="button"
                              className="btn-primary"
                              disabled={busy}
                              onClick={() => respond(item.id, 'accepted')}
                            >
                              Accept
                            </button>
                            <button
                              type="button"
                              className="btn-secondary"
                              disabled={busy}
                              onClick={() => respond(item.id, 'rejected')}
                            >
                              Reject
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {subTab === 'feed' && (
        <Hackathons
          key={tabEpoch}
          onBrowseTeams={eventId => {
            // The event travels in the URL so the filtered view is shareable,
            // same reason the sub-tab itself lives in `?teamtab=`.
            const url = new URL(window.location.href);
            url.searchParams.set('teamtab', 'discover');
            url.searchParams.set('event', String(eventId));
            window.history.replaceState({}, '', url);
            setHackathonFilter(String(eventId));
            setSubTab('discover');
            setDetailId(null);
            setShowCreate(false);
          }}
        />
      )}
    </div>
  );
}
