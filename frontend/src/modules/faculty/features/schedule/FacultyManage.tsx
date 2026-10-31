import { useState, useEffect } from 'react';
import { Card } from '@/components/ui';
import { Plus, Clock } from 'lucide-react';

type ManageSubTab = 'extra' | 'quiz' | 'created';

const SUB_TAB_LABELS: Record<ManageSubTab, string> = {
  extra: 'Extra Class',
  quiz: 'Quiz',
  created: 'Created',
};

type CreatedEvent = {
  id: number;
  course_code: string;
  label: string;
  event_date: string;
  time_slot: string;
  cancelled: boolean;
};

/** Shared form for adding an extra class or quiz. */
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

  const input = { className: 'w-full rounded px-3 py-2 text-sm bg-[var(--cp-bg)] border border-[var(--cp-border)] text-[var(--cp-text)]' };
  const filteredCourses = courses.filter(
    c => (selectedSemester == null || c.semester === selectedSemester) &&
         (!selectedBranch || c.branch === selectedBranch) &&
         (!selectedInstructor || c.instructor === selectedInstructor)
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCode || !label || !dateStr || !timeSlot) {
      _setStatus('error'); _setStatusMsg('Please fill in all fields.'); return;
    }
    _setStatus('idle');
    try {
      const res = await fetch('/extra-events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          course_code: selectedCode, label, event_date: dateStr, time_slot: timeSlot,
          semester: selectedSemester, branch: selectedBranch || undefined, instructor_name: selectedInstructor || undefined,
        }),
      });
      if (!res.ok) throw new Error(`Server responded ${res.status}`);
      _setStatus('ok'); _setStatusMsg(`${subTab === 'quiz' ? 'Quiz' : 'Extra class'} added — visible in Live Schedule.`);
      setSelectedCode(''); setLabel(subTab === 'quiz' ? 'Quiz-1' : 'Extraclass'); setDateStr(''); setTimeSlot('');
      setSelectedSemester(null); setSelectedBranch(''); setSelectedInstructor('');
    } catch { _setStatus('error'); _setStatusMsg('Failed to add extra event. Try again.'); }
  };

  const HOURS = Array.from({ length: 9 }, (_, i) => i + 9);
  const MINUTES = Array.from({ length: 60 }, (_, i) => i);
  const pad = (n: number) => n.toString().padStart(2, '0');

  return (
    <Card>
      <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--cp-text)' }}>
        {subTab === 'quiz' ? 'Add Quiz' : 'Add Extra Class'}
      </h2>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>Semester</label>
          <select value={selectedSemester ?? ''} onChange={e => setSelectedSemester(e.target.value ? Number(e.target.value) : null)} className={input.className}>
            <option value="">Select semester</option>
            {options.semesters.map(s => <option key={s} value={s}>{s} Sem</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>Branch</label>
          <select value={selectedBranch} onChange={e => setSelectedBranch(e.target.value)} className={input.className}>
            <option value="">Select branch</option>
            {options.branches.map(b => <option key={b} value={b}>{b}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>Instructor</label>
          <select value={selectedInstructor} onChange={e => setSelectedInstructor(e.target.value)} className={input.className}>
            <option value="">Select instructor</option>
            {options.instructors.map(i => <option key={i} value={i}>{i}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>Course Code</label>
          <select value={selectedCode} onChange={e => setSelectedCode(e.target.value)} className={input.className}>
            <option value="">Select course</option>
            {filteredCourses.map(c => <option key={c.code} value={c.code}>{c.code} — {c.name}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>Label</label>
          <input type="text" value={label} onChange={e => setLabel(e.target.value)} placeholder="e.g. Extraclass, Quiz-1" className={input.className} />
        </div>
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>Date</label>
          <input type="date" value={dateStr} onChange={e => setDateStr(e.target.value)} className={input.className} />
        </div>
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>Time slot</label>
          <div className="flex gap-2">
            <div className="relative inline-block w-full">
              <input type="text" value={timeSlot ? `${timeSlot.split(':')[0].padStart(2,'0')}:${timeSlot.split(':')[1].padStart(2,'0')}` : ''} readOnly placeholder="HH:mm" className="w-full rounded px-3 py-2 text-sm bg-[var(--cp-bg)] border border-[var(--cp-border)] text-[var(--cp-text)] cursor-pointer" />
            </div>
            <button type="button" className="rounded px-3 py-2 text-xs bg-[var(--cp-surface)] border border-[var(--cp-border)] text-[var(--cp-text)]">Check vacant</button>
          </div>
        </div>
        <button type="submit" className="inline-flex items-center gap-2 rounded px-4 py-2 text-sm font-medium bg-[var(--cp-primary)] text-white hover:brightness-110 transition">
          <Plus size={16} /> Add {subTab === 'quiz' ? 'Quiz' : 'Extra Class'}
        </button>
      </form>
    </Card>
  );
}

  const [_events, _setEvents] = useState<any[]>([]);
  const [_loading, _setLoading] = useState(true);
  useEffect(() => {
    fetch('/extra-events/options')
      .then(r => r.json())
      .then((_data: any) => {
        setEvents([]); // demo data — fetch from /extra-events endpoint
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [onRefresh]);
  
  const demoEvents = [
    { id: 1, course_code: 'CS8004', label: subTab === 'quiz' ? 'Quiz 1 - Mid Sem' : 'Extra Class', event_date: '2026-11-02', time_slot: '09:00', cancelled: false },
    { id: 2, course_code: 'CS8004', label: subTab === 'quiz' ? 'Quiz 2 - End Sem' : 'Extra Class - Revision', event_date: '2026-11-05', time_slot: '13:00', cancelled: false },
  ];

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold" style={{ color: 'var(--cp-text)' }}>
          Created {subTab === 'quiz' ? 'Quizzes' : 'Extra Classes'}
        </h3>
        <span className="text-xs rounded-full bg-[var(--cp-surface)] px-2 py-0.5 font-medium" style={{ color: 'var(--cp-primary)' }}>
          {demoEvents.length} active
        </span>
      </div>
      <div className="space-y-2">
        {demoEvents.map(ev => (
          <div key={ev.id} className="p-3 rounded border flex items-center justify-between" style={{ background: 'var(--cp-bg)', borderColor: 'var(--cp-border)' }}>
            <div>
              <div className="font-mono font-semibold text-sm" style={{ color: 'var(--cp-text)' }}>{ev.course_code}</div>
              <div className="text-sm" style={{ color: 'var(--cp-text)' }}>{ev.label}</div>
              <div className="text-xs" style={{ color: 'var(--cp-muted)' }}>{ev.event_date} · {ev.time_slot}</div>
            </div>
            <div className="flex gap-2">
              <button type="button" onClick={() => alert(`Update: ${ev.label}`)} className="text-xs rounded px-2 py-0.5 bg-amber-500/20 text-amber-600">Update</button>
              <button type="button" onClick={() => alert(`Cancel: ${ev.label}`)} className="text-xs rounded px-2 py-0.5 bg-red-500/20 text-red-600">Cancel</button>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function FacultyManage() {
  const [subTab, setSubTab] = useState<ManageSubTab>('extra');
  const [_refreshKey, _setRefreshKey] = useState(0);
  const [notification, setNotification] = useState('');
  const [options, setOptions] = useState<{ semesters: number[]; branches: string[]; instructors: string[]; courses: Array<{code: string; name: string; semester?: number; branch?: string; instructor?: string}>; timetable_entries: any[]; profile: any } | null>(null);
  const [optionsLoading, setOptionsLoading] = useState(false);

  useEffect(() => {
    setOptionsLoading(true);
    fetch('/extra-events/options')
      .then(r => r.json())
      .then((data: any) => setOptions({
        semesters: data.semesters || [],
        branches: data.branches || [],
        instructors: data.instructors || [],
        courses: data.courses || [],
        timetable_entries: data.timetable_entries || [],
        profile: data.profile || null,
      }))
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
      {/* Sub-tabs */}
      <div className="flex gap-2 items-center overflow-x-auto w-full max-w-xl px-2 pb-1.5">
        <nav className="flex gap-2 shrink-0" aria-label="Manage sub-tabs">
          {(['extra', 'quiz'] as ManageSubTab[]).map(id => {
            const isActive = subTab === id;
            return (
              <button
                key={id}
                type="button"
                onClick={() => setSubTab(id)}
                aria-current={isActive ? 'page' : undefined}
                className="inline-flex items-center justify-center gap-2 px-3 py-1.5 text-sm font-medium whitespace-nowrap rounded-lg transition-all duration-200"
                style={
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
        {notification && (
          <div className="flex items-center gap-2 ml-auto shrink-0">
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/20 text-amber-600 px-2 py-0.5 text-xs font-medium">
              <Clock size={10} strokeWidth={2.5} aria-hidden /> New
            </span>
            <span className="text-xs font-medium truncate" style={{ color: 'var(--cp-text)' }}>{notification}</span>
            <button onClick={() => setNotification('')} className="text-xs underline" style={{ color: 'var(--cp-muted)' }}>Dismiss</button>
          </div>
        )}
      </div>

      {subTab === 'extra' ? (
        <>
          <ExtraEventForm subTab="extra" courses={options.courses} options={options} />
        </>
      ) : (
        <>
          <ExtraEventForm subTab="quiz" courses={options.courses} options={options} />
        </>
      )}
    </div>
  );
}
