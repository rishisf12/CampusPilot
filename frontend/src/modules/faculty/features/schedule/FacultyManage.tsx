import { useState, useEffect } from 'react';
import { Card } from '@/components/ui';
import { Plus } from 'lucide-react';
import useProfile from '@shared/hooks/useProfile';

type ManageSubTab = 'extra' | 'quiz' | 'created';

const SUB_TAB_LABELS: Record<ManageSubTab, string> = {
  extra: 'Extra Class',
  quiz: 'Quiz',
  created: 'Created',
};

const pad = (n: number) => n.toString().padStart(2, '0');

const HOURS = [9, 10, 11, 12, 13, 14, 15, 16, 17];
const MINUTES = [0, 15, 30, 45];

function TimePicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false);
  const [hour, setHour] = useState<number | null>(value ? Number(value.split(':')[0]) : null);
  const [minute, setMinute] = useState<number | null>(value ? Number(value.split(':')[1]) : null);

  const formatted = hour != null && minute != null ? pad(hour) + ':' + pad(minute) : '';

  const hourBtnClass = (h: number) => hour === h ? 'bg-[var(--cp-primary)] text-white' : 'text-[var(--cp-text)] hover:bg-[var(--cp-surface)]';
  const minBtnClass = (m: number) => minute === m ? 'bg-[var(--cp-primary)] text-white' : 'text-[var(--cp-text)] hover:bg-[var(--cp-surface)]';

  return (
    <div className="relative inline-block w-full">
      <div className="flex gap-2">
        <div className="flex-1 relative">
          <input
            type="text"
            value={formatted}
            onFocus={() => setOpen(true)}
            onBlur={() => setOpen(false)}
            readOnly
            placeholder="--:--"
            className="w-full rounded px-3 py-2 text-sm bg-[var(--cp-bg)] border border-[var(--cp-border)] text-[var(--cp-text)] cursor-pointer"
          />
          {open && (
            <div className="absolute z-50 mt-1 w-full max-h-64 overflow-y-auto bg-[var(--cp-bg)] border border-[var(--cp-border)] rounded shadow-lg">
              <div className="flex gap-4 px-2 py-2">
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-[var(--cp-muted)] mb-1">Hour</span>
                  {HOURS.map((h) => (
                    <button key={h} type="button" onClick={() => { setHour(h); if (minute != null) onChange(pad(h) + ':' + pad(minute)); setOpen(false); }} className={`w-8 h-8 rounded text-sm font-medium ${hourBtnClass(h)}`}>
                      {pad(h)}
                    </button>
                  ))}
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-[var(--cp-muted)] mb-1">Minute</span>
                  {MINUTES.map((m) => (
                    <button key={m} type="button" onClick={() => { setMinute(m); if (hour != null) onChange(pad(hour) + ':' + pad(m)); setOpen(false); }} className={`w-8 h-8 rounded text-sm font-medium ${minBtnClass(m)}`}>
                      {pad(m)}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ExtraEventForm({
  subTab,
  courses,
  options,
}: {
  subTab: 'extra' | 'quiz';
  courses: Array<{ code: string; name: string; semester?: number; branch?: string; instructor?: string }>;
  options: { semesters: number[]; branches: string[]; instructors: string[]; courses: Array<{ code: string; name: string; semester?: number; branch?: string; instructor?: string }>; timetable_entries: any[]; profile: any };
}) {
  const [selectedCode, setSelectedCode] = useState('');
  const [selectedSemester, setSelectedSemester] = useState<number | null>(null);
  const [selectedBranch, setSelectedBranch] = useState('');
  const [selectedInstructor, setSelectedInstructor] = useState('');
  const [label, setLabel] = useState(subTab === 'quiz' ? 'Quiz-1' : 'Extraclass');
  const [dateStr, setDateStr] = useState('');
  const [timeSlot, setTimeSlot] = useState('');
  const [status, setStatus] = useState<'idle' | 'ok' | 'error'>('idle');
  const [statusMsg, setStatusMsg] = useState('');

  const input = { className: 'w-full rounded px-3 py-2 text-sm bg-[var(--cp-bg)] border border-[var(--cp-border)] text-[var(--cp-text)]' };
  const filteredCourses = courses.filter((c) => (selectedSemester == null || c.semester === selectedSemester) && (!selectedBranch || c.branch === selectedBranch) && (!selectedInstructor || c.instructor === selectedInstructor));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCode || !label || !dateStr || !timeSlot) {
      setStatus('error');
      setStatusMsg('Please fill in all fields.');
      return;
    }
    setStatus('idle');
    try {
      const res = await fetch('/extra-events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ course_code: selectedCode, label, event_date: dateStr, time_slot: timeSlot, semester: selectedSemester, branch: selectedBranch || undefined, instructor_name: selectedInstructor || undefined }),
      });
      if (!res.ok) throw new Error('Server responded ' + res.status);
      setStatus('ok');
      setStatusMsg(subTab === 'quiz' ? 'Quiz added' : 'Extra class added');
      setSelectedCode('');
      setLabel(subTab === 'quiz' ? 'Quiz-1' : 'Extraclass');
      setDateStr('');
      setTimeSlot('');
      setSelectedSemester(null);
      setSelectedBranch('');
      setSelectedInstructor('');
    } catch {
      setStatus('error');
      setStatusMsg('Failed to add extra event. Try again.');
    }
  };

  return (
    <Card>
      <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--cp-text)' }}>{subTab === 'quiz' ? 'Add Quiz' : 'Add Extra Class'}</h2>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>Course</label>
          <select value={selectedCode} onChange={(e) => setSelectedCode(e.target.value)} className={input.className}>
            <option value="">Select course</option>
            {filteredCourses.map((c: any) => (
              <option key={c.code} value={c.code}>{c.code} — {c.name} {c.is_extra ? '(Extra)' : ''}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>Semester</label>
          <select value={selectedSemester ?? ''} onChange={(e) => setSelectedSemester(e.target.value ? Number(e.target.value) : null)} className={input.className}>
            <option value="">Select semester</option>
            {(options.semesters || []).map((s: number) => <option key={s} value={s}>{s} Sem</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>Branch</label>
          <select value={selectedBranch} onChange={(e) => setSelectedBranch(e.target.value)} className={input.className}>
            <option value="">Select branch</option>
            {(options.branches || []).map((b: string) => <option key={b} value={b}>{b}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>Instructor</label>
          <select value={selectedInstructor} onChange={(e) => setSelectedInstructor(e.target.value)} className={input.className}>
            <option value="">Select instructor</option>
            {(options.instructors || []).map((i: string) => <option key={i} value={i}>{i}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>Date</label>
          <input type="date" value={dateStr} onChange={(e) => setDateStr(e.target.value)} className={input.className} />
        </div>
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>Time slot (vacant room lookup applies)</label>
          <div className="flex gap-2">
            <TimePicker value={timeSlot} onChange={setTimeSlot} />
          </div>
        </div>
        <button type="submit" className="inline-flex items-center gap-2 rounded px-4 py-2 text-sm font-medium bg-[var(--cp-primary)] text-white hover:brightness-110 transition w-full md:w-auto">
          <Plus size={16} /> Add {subTab === 'quiz' ? 'Quiz' : 'Extra Class'}
        </button>
        {status === 'ok' && <p className="text-sm text-emerald-600 mt-2">{statusMsg}</p>}
        {status === 'error' && <p className="text-sm text-red-600 mt-2">{statusMsg}</p>}
      </form>
      {selectedCode && (
        <div className="mt-3 p-3 rounded text-xs bg-[var(--cp-surface)] border border-[var(--cp-border)]" style={{ color: 'var(--cp-text)' }}>
          Selected: <b>{selectedCode}</b>
        </div>
      )}
    </Card>
  );
}

function CreatedEventsList() {
  return (
    <Card>
      <h3 className="text-base font-semibold mb-3" style={{ color: 'var(--cp-text)' }}>
        Created Extra Classes / Quizzes
      </h3>
      <div className="space-y-2">
        <div className="p-2.5 rounded border" style={{ background: 'var(--cp-bg)', borderColor: 'var(--cp-border)' }}>
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono font-semibold text-sm" style={{ color: 'var(--cp-text)' }}>
              CS8004
            </span>
            <span className="text-xs" style={{ color: 'var(--cp-muted)' }}>
              Extra Class — Mon 9:00–9:55 — Room L-105
            </span>
          </div>
          <div className="flex gap-2 mt-1">
            <button type="button" className="text-xs rounded px-2 py-0.5 bg-amber-500/20 text-amber-600">
              Update
            </button>
            <button type="button" className="text-xs rounded px-2 py-0.5 bg-red-500/20 text-red-600">
              Cancel
            </button>
            <span className="text-xs ml-auto" style={{ color: 'var(--cp-muted)' }}>
              Active
            </span>
          </div>
        </div>
      </div>
    </Card>
  );
}

export default function FacultyManage() {
  const [options, setOptions] = useState<any>(null);
  const [optionsLoading, setOptionsLoading] = useState(false);
  const [subTab, setSubTab] = useState<ManageSubTab>('extra');

  useEffect(() => {
    setOptionsLoading(true);
    fetch('/extra-events/options')
      .then((r) => r.json())
      .then((data) => {
        setOptions({
          semesters: data.semesters || [],
          branches: data.branches || [],
          instructors: data.instructors || [],
          courses: data.courses || [],
          timetable_entries: data.timetable_entries || [],
          profile: data.profile || null,
        });
      })
      .catch(() => setOptions({ semesters: [], branches: [], instructors: [], courses: [], timetable_entries: [], profile: null }))
      .finally(() => setOptionsLoading(false));
  }, []);

  if (optionsLoading || !options) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="animate-spin rounded-full border-2 border-current border-t-transparent" style={{ color: 'var(--cp-primary)', width: 26, height: 26 }} />
      </div>
    );
  }

  return (
    <div className="space-y-4 max-w-xl mx-auto">
      <div className="flex gap-2 overflow-x-auto w-full max-w-xl px-2 pb-1.5">
        <nav className="flex gap-2 shrink-0" aria-label="Manage sub-tabs">
          {(['extra', 'quiz', 'created'] as ManageSubTab[]).map((id) => {
            const isActive = subTab === id;
            return (
              <button key={id} type="button" onClick={() => setSubTab(id)} aria-current={isActive ? 'page' : undefined} className="inline-flex items-center justify-center gap-2 px-3 py-1.5 text-sm font-medium whitespace-nowrap rounded-lg transition-all duration-200" style={
                isActive
                  ? { borderRadius: '0.5rem', background: 'var(--cp-surface)', color: 'var(--cp-primary)', boxShadow: 'var(--cp-clay)', border: '1px solid rgba(255,255,255,.22)' }
                  : { borderRadius: '0.5rem', background: 'rgba(255,255,255,.06)', color: 'var(--cp-text)', border: '1px solid rgba(163,177,198,.3)' }
                }
              >
                {SUB_TAB_LABELS[id]}
              </button>
            );
          })}
        </nav>
      </div>

      {subTab === 'extra' ? (
        <ExtraEventForm subTab="extra" courses={options.courses} options={options} />
      ) : subTab === 'quiz' ? (
        <ExtraEventForm subTab="quiz" courses={options.courses} options={options} />
      ) : (
        <CreatedEventsList />
      )}
    </div>
  );
}
