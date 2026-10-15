import { useProfile } from '../../hooks/useProfile';
import { profileApi, scheduleApi } from '../../../api';
import {
  BRANCH_OPTIONS,
  GROUP_PROGRAMMES,
  PROGRAMMES,
  PROGRAMME_BRANCHES,
  PROGRAMME_SEMESTERS,
  programmeGroupOf,
  type BranchOption,
  type Programme,
} from '../../constants';
import { useState, useMemo } from 'react';
import { Plus, RefreshCw, Save, X } from 'lucide-react';
import { Badge, Button, Card, Input, Select } from '@/components/ui';
import Spinner from '../../components/Spinner';
import ManagePasskeys from '../../auth/ManagePasskeys';
import type { ExtraCourseResponse } from '../../types/api';

/**
 * Profile settings page.
 *
 * Lets the student edit their programme, semester, branch, electives,
 * extra courses and attendance target. Branch change requests are handled
 * here as well. All data lives in the ProfileProvider context so changes
 * propagate to the timetable, attendance, rooms and exam views immediately.
 *
 * Programme and branch stay in step: the branch list follows the selected
 * programme, the same pairing signup established, so a master's student can
 * never land on an undergraduate branch. Changing the programme also changes
 * the feature bundle on the next render - the shell reads it from here.
 */
export default function Profile() {
  const {
    loading,
    error,
    refresh,
    branch,
    semester: profileSemester,
    programme: profileProgramme,
    attendanceTarget,
    extraCourses,
    branchChange,
  } = useProfile();

  const [target, setTarget] = useState(attendanceTarget);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  // Local state for form fields that need immediate UI updates
  const [programme, setProgramme] = useState(profileProgramme);
  const [semester, setSemester] = useState(profileSemester);
  const [branchState, setBranch] = useState(branch);

  // Branch change state
  const [branchFrom, setBranchFrom] = useState(branchChange.from || branch || '');
  const [branchTo, setBranchTo] = useState(branchChange.to || '');
  const [noBranchChange, setNoBranchChange] = useState(!branchChange.requested);

  // Elective/extra course state
  const [extraCode, setExtraCode] = useState('');
  const [extraInstructor, setExtraInstructor] = useState('');
  const [extraCoursesList, setExtraCoursesList] = useState<ExtraCourseResponse[]>(
    extraCourses || []
  );

  const semesters = useMemo(
    () =>
      programme
        ? PROGRAMME_SEMESTERS[programme as keyof typeof PROGRAMME_SEMESTERS] ||
          PROGRAMME_SEMESTERS.BTech
        : [],
    [programme]
  );

  /** Branches valid for the selected programme; the full list as fallback. */
  const branchOptions = useMemo<readonly BranchOption[]>(() => {
    if (programme && PROGRAMME_BRANCHES[programme as Programme]) {
      return PROGRAMME_BRANCHES[programme as Programme];
    }
    return BRANCH_OPTIONS;
  }, [programme]);

  /**
   * Programmes the student may switch between.
   *
   * The group chosen at signup is fixed: a BTech student may move to BDes (and
   * an MTech student to MDes) but never across groups, so a master's student is
   * not offered undergraduate branches and semesters. Derived from the *saved*
   * programme (not the editable one) so the list cannot drift mid-edit. A
   * profile with no programme yet keeps the full list so it can be set once.
   */
  const programmeChoices = useMemo<readonly string[]>(
    () => (profileProgramme ? GROUP_PROGRAMMES[programmeGroupOf(profileProgramme)] : PROGRAMMES),
    [profileProgramme]
  );

  const clearMessages = () => {
    setMessage(null);
    setLocalError(null);
  };

  const save = async () => {
    setSaving(true);
    setMessage(null);
    setLocalError(null);
    try {
      await profileApi.update({
        programme,
        semester: Number(semester),
        branch: branchState,
        attendance_target: Number(target),
      });
      // Update local state to match saved values
      setProgramme(programme);
      setSemester(Number(semester));
      setBranch(branchState);
      // Refresh the profile context so all dependent screens update
      await refresh();
      setMessage('Profile saved');
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Failed to save profile');
    } finally {
      setSaving(false);
    }
  };

  const submitBranchChange = async () => {
    setMessage(null);
    setLocalError(null);
    try {
      if (noBranchChange) {
        const result = await profileApi.clearBranchChange();
        setMessage(result.message);
        setBranchTo('');
        setNoBranchChange(true);
      } else {
        if (!branchTo) {
          setLocalError('Select the branch you want to move to');
          return;
        }
        const result = await profileApi.requestBranchChange({
          from_branch: branchFrom,
          to_branch: branchTo,
        });
        setMessage(result.message);
        setBranchTo('');
        setBranchFrom(branchTo);
        setNoBranchChange(true);
        await refresh();
      }
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Branch change failed');
    }
  };

  const addExtraCourse = async () => {
    const code = extraCode.trim().toUpperCase();
    const instructor = extraInstructor.trim();
    if (!code) return;
    try {
      const created = await scheduleApi.addExtra({
        code,
        name: code, // Use code as name placeholder; can be updated later
        instructor: instructor || undefined,
        semester: Number(semester),
        branch,
      });
      setExtraCoursesList(prev => [...prev, created]);
      setExtraCode('');
      setExtraInstructor('');
      await refresh();
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Failed to add course');
    }
  };

  const removeExtraCourse = async (code: string) => {
    try {
      await scheduleApi.removeExtra(code);
      setExtraCoursesList(prev => prev.filter(c => c.code !== code));
      await refresh();
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Failed to remove course');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner size={32} />
      </div>
    );
  }

  if (error) {
    return (
      <Card className="space-y-3" style={{ borderColor: 'rgba(239,68,68,.35)' }}>
        <p className="text-danger-700">{error}</p>
        <Button
          type="button"
          variant="primary"
          size="sm"
          icon={
            <RefreshCw size={16} strokeWidth={2} aria-hidden style={{ color: 'currentColor' }} />
          }
          onClick={() => {
            window.location.reload();
          }}
        >
          Reload
        </Button>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-gray-900">Profile Settings</h2>

      {/* Programme & Semester */}
      <Card className="space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Programme & Semester</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <span className="label">Programme</span>
            <Select
              value={programme || ''}
              onChange={e => {
                clearMessages();
                const newProgramme = e.target.value;
                setProgramme(newProgramme);
                // Reset semester to first valid option for the new programme
                const newSemesters =
                  PROGRAMME_SEMESTERS[newProgramme as keyof typeof PROGRAMME_SEMESTERS] ||
                  PROGRAMME_SEMESTERS.BTech;
                setSemester(newSemesters[0]);
                // The branch list belongs to the programme: keep the current
                // branch only if the new programme allows it.
                const allowed = PROGRAMME_BRANCHES[newProgramme as Programme];
                if (allowed && branchState && !allowed.includes(branchState as BranchOption)) {
                  setBranch(allowed[0]);
                }
              }}
            >
              {programmeChoices.map(p => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <span className="label">Semester</span>
            <Select
              value={semester ?? ''}
              onChange={e => {
                clearMessages();
                setSemester(Number(e.target.value));
              }}
            >
              {semesters.map(s => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          </div>
        </div>
      </Card>

      {/* Branch */}
      <Card className="space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Branch</h3>
        <Select
          value={branchState}
          onChange={e => {
            clearMessages();
            setBranch(e.target.value);
          }}
        >
          <option value="">Select branch</option>
          {branchOptions.map(b => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </Select>
      </Card>

      {/* Elective/Extra/Backlog courses */}
      <Card className="space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Elective/Extra/Backlog courses</h3>
        <p className="text-xs text-gray-500">
          Add courses using either course code or instructor name (as mentioned in timetable). The
          timetable is filtered by your semester, so if either field matches, we can find the room
          number and fill in unknown information from known data.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <Input
            className="font-mono"
            value={extraCode}
            onChange={e => setExtraCode(e.target.value.toUpperCase())}
            placeholder="Course code (e.g. CS501)"
            onKeyDown={e => e.key === 'Enter' && addExtraCourse()}
          />
          <Input
            value={extraInstructor}
            onChange={e => setExtraInstructor(e.target.value)}
            placeholder="Instructor name (as in timetable)"
            onKeyDown={e => e.key === 'Enter' && addExtraCourse()}
          />
        </div>
        <Button
          type="button"
          variant="primary"
          size="sm"
          icon={<Plus size={16} strokeWidth={2} aria-hidden style={{ color: 'currentColor' }} />}
          onClick={addExtraCourse}
          className="whitespace-nowrap w-full sm:w-auto"
        >
          Add
        </Button>
        {extraCoursesList.length > 0 && (
          <ul className="flex flex-wrap gap-2">
            {extraCoursesList.map(c => (
              <li key={c.code}>
                <Badge tone="neutral" className="!py-1.5 !pl-3 !pr-1.5">
                  <span className="font-mono">{c.code}</span>
                  {c.instructor && <span className="text-xs opacity-70">— {c.instructor}</span>}
                  <button
                    type="button"
                    onClick={() => removeExtraCourse(c.code)}
                    aria-label={`Remove ${c.code}`}
                    className="ml-1 inline-flex items-center justify-center rounded-full p-1 transition-colors hover:bg-black/5"
                  >
                    <X size={14} strokeWidth={2} aria-hidden style={{ color: 'currentColor' }} />
                  </button>
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Attendance target */}
      <Card className="space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Attendance Target</h3>
        <div className="flex items-center gap-2">
          <Input
            type="number"
            min="0"
            max="100"
            className="w-28"
            value={target}
            onChange={e => setTarget(Number(e.target.value))}
          />
          <span className="text-xs text-gray-500">
            Used by the Attendance tab for risk colouring.
          </span>
        </div>
      </Card>

      {/* Branch change request */}
      <Card className="space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Branch Change Request</h3>
        {branchChange.requested && branchChange.to && (
          <div className="p-2.5 rounded-lg border border-primary-200 bg-primary-50 text-primary-700 text-sm">
            Pending request: {branchChange.from} &rarr; {branchChange.to}
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <span className="label">From branch</span>
            <Select value={branchFrom} onChange={e => setBranchFrom(e.target.value)}>
              <option value="">Select branch</option>
              {branchOptions.map(b => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <span className="label">To branch</span>
            <Select
              value={branchTo}
              disabled={noBranchChange}
              onChange={e => setBranchTo(e.target.value)}
            >
              <option value="">Select branch</option>
              {branchOptions.map(b => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </Select>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={noBranchChange}
              onChange={e => setNoBranchChange(e.target.checked)}
              className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            No branch change (cancel pending)
          </label>
        </div>
        <div className="flex justify-start">
          <Button
            type="button"
            variant="primary"
            size="sm"
            onClick={submitBranchChange}
            disabled={!noBranchChange && !branchTo}
          >
            {noBranchChange ? 'Cancel pending request' : 'Submit branch change'}
          </Button>
        </div>
      </Card>

      {/* Save button & messages */}
      {message && (
        <div className="rounded-lg bg-success-50 border border-success-200 px-3 py-2 text-xs text-success-800">
          {message}
        </div>
      )}
      {localError && (
        <div className="rounded-lg bg-danger-50 border border-danger-200 px-3 py-2 text-xs text-danger-800">
          {localError}
        </div>
      )}
      <div className="flex justify-start">
        <Button
          type="button"
          variant="primary"
          size="sm"
          icon={<Save size={16} strokeWidth={2} aria-hidden style={{ color: 'currentColor' }} />}
          loading={saving}
          onClick={save}
          disabled={saving}
        >
          Save profile
        </Button>
      </div>

      {/* Passkeys */}
      <ManagePasskeys />
    </div>
  );
}
