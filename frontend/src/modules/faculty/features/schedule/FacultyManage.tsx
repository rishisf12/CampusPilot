import { useState, useEffect } from 'react';
import { Card } from '@/components/ui';
import { Plus } from 'lucide-react';

type ManageSubTab = 'extra' | 'quiz' | 'created';

const SUB_TAB_LABELS: Record<ManageSubTab, string> = {
  extra: 'Extra Class',
  quiz: 'Quiz',
  created: 'Created',
};

function ExtraEventForm({ subTab, courses, options }: { subTab: ManageSubTab; courses: Array<{code: string; name: string}>; options: any }) {
  const [selectedSemester, setSelectedSemester] = useState<number | null>(null);
  const [selectedBranch, setSelectedBranch] = useState('');
  const [selectedInstructor, setSelectedInstructor] = useState('');
  const [selectedCode, setSelectedCode] = useState('');
  const [label, setLabel] = useState(subTab === 'quiz' ? 'Quiz-1' : 'Extraclass');
  const [dateStr, setDateStr] = useState('');
  const [timeSlot, setTimeSlot] = useState('');
  const [status, setStatus] = useState<'idle' | 'ok' | 'error'>('idle');
  const [statusMsg, setStatusMsg] = useState('');

  const input = { className: 'w-full rounded px-3 py-2 text-sm bg-[var(--cp-bg)] border border-[var(--cp-border)] text-[var(--cp-text)]' };
  const filtered = courses.filter((c: any) =>
    (selectedSemester == null || c.semester === selectedSemester) &&
    (!selectedBranch || c.branch === selectedBranch) &&
    (!selectedInstructor || c.instructor === selectedInstructor)
  );

  return (
    <Card>
      <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--cp-text)' }}>
        {subTab === 'quiz' ? 'Add Quiz' : 'Add Extra Class'}
      </h2>
      <form onSubmit={async (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedCode || !label || !dateStr || !timeSlot) {
          setStatus('error'); setStatusMsg('Please fill in all fields.'); return;
        }
        try {
          const res = await fetch('/extra-events', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              course_code: selectedCode, label, event_date: dateStr, time_slot: timeSlot,
              semester: selectedSemester, branch: selectedBranch || undefined, instructor_name: selectedInstructor || undefined,
            }),
          });
          if (!res.ok) throw new Error('Server error');
          setStatus('ok'); setStatusMsg(`${subTab === 'quiz' ? 'Quiz' : 'Extra class'} added — visible in Live Schedule.`);
          setSelectedCode(''); setLabel(subTab === 'quiz' ? 'Quiz-1' : 'Extraclass'); setDateStr(''); setTimeSlot(''); setSelectedSemester(null); setSelectedBranch(''); setSelectedInstructor('');
        } catch {
          setStatus('error'); setStatusMsg('Failed to add extra event. Try again.');
        }
      }} className="space-y-3">
        <div><label className="block text-sm mb-1">Semester</label>
          <select value={selectedSemester ?? ''} onChange={e => setSelectedSemester(e.target.value ? Number(e.target.value) : null)} className={input.className}>
            <option value="">Select semester</option>
            {(options.semesters || []).map((s: number) => <option key={s} value={s}>{s} Sem</option>)}
          </select>
        </div>
        <div><label className="block text-sm mb-1">Branch</label>
          <select value={selectedBranch} onChange={e => setSelectedBranch(e.target.value)} className={input.className}>
            <option value="">Select branch</option>
            {(options.branches || []).map((b: string) => <option key={b} value={b}>{b}</option>)}
          </select>
        </div>
        <div><label className="block text-sm mb-1">Instructor</label>
          <select value={selectedInstructor} onChange={e => setSelectedInstructor(e.target.value)} className={input.className}>
            <option value="">Select instructor</option>
            {(options.instructors || []).map((i: string) => <option key={i} value={i}>{i}</option>)}
          </select>
        </div>
        <div><label className="block text-sm mb-1">Course Code</label>
          <select value={selectedCode} onChange={e => setSelectedCode(e.target.value)} className={input.className}>
            <option value="">Select course</option>
            {filtered.map((c: any) => <option key={c.code} value={c.code}>{c.code} — {c.name}</option>)}
          </select>
        </div>
        <div><label className="block text-sm mb-1">Label</label>
          <input type="text" value={label} onChange={e => setLabel(e.target.value)} placeholder="e.g. Extraclass, Quiz-1" className={input.className} />
        </div>
        <div><label className="block text-sm mb-1">Date</label>
          <input type="date" value={dateStr} onChange={e => setDateStr(e.target.value)} className={input.className} />
        </div>
        <div><label className="block text-sm mb-1">Time slot</label>
          <input type="text" value={timeSlot} onChange={e => setTimeSlot(e.target.value)} placeholder="HH:mm" className={input.className} />
        </div>
        <button type="submit" className="inline-flex items-center gap-2 rounded px-4 py-2 text-sm font-medium bg-[var(--cp-primary)] text-white">+ Add {subTab === 'quiz' ? 'Quiz' : 'Extra Class'}</button>
        {status === 'ok' && <p className="text-sm text-emerald-600">{statusMsg}</p>}
        {status === 'error' && <p className="text-sm text-red-600">{statusMsg}</p>}
      </form>
    </Card>
  );
}

function CreatedEventsList() {
  return (
    <Card>
      <h3 className="text-base font-semibold mb-3">Created Extra Classes / Quizzes</h3>
      <div className="space-y-2">
        <div className="p-2.5 rounded border flex items-center justify-between" style={{ background: 'var(--cp-bg)' }}>
          <div>
            <div className="font-mono font-semibold text-sm">CS8004</div>
            <div className="text-sm">Extra Class — Mon 9:00–9:55 — Room L-105</div>
          </div>
          <div className="flex gap-2">
            <button className="text-xs rounded px-2 py-0.5 bg-amber-500/20 text-amber-600">Update</button>
            <button className="text-xs rounded px-2 py-0.5 bg-red-500/20 text-red-600">Cancel</button>
            <span className="text-xs">Active</span>
          </div>
        </div>
      </div>
    </Card>
  );
}

export default function FacultyManage() {
  const [subTab, setSubTab] = useState<ManageSubTab>('extra');
  const [options, setOptions] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetch('/extra-events/options')
      .then(r => r.json())
      .then(data => setOptions({ semesters: data.semesters || [], branches: data.branches || [], instructors: data.instructors || [], courses: data.courses || [], timetable_entries: data.timetable_entries || [], profile: data.profile || null }))
      .catch(() => setOptions({ semesters: [], branches: [], instructors: [], courses: [], timetable_entries: [], profile: null }))
      .finally(() => setLoading(false));
  }, []);

  if (loading || !options) return <div className="flex justify-center py-16"><div className="animate-spin rounded-full border-2 border-current w-8 h-8" /></div>;

  return (
    <div className="space-y-4 max-w-xl mx-auto">
      <div className="flex gap-2 items-center overflow-x-auto w-full max-w-xl px-2 pb-1.5">
        <nav className="flex gap-2 shrink-0" aria-label="Manage sub-tabs">
          {(['extra', 'quiz', 'created'] as ManageSubTab[]).map(id => (
            <button key={id} onClick={() => setSubTab(id)} className={`px-3 py-1.5 text-sm rounded-lg ${subTab === id ? 'bg-[var(--cp-surface)] text-[var(--cp-primary)]' : 'bg-[rgba(255,255,255,.06)] text-[var(--cp-text)]'}`}>
              {SUB_TAB_LABELS[id]}
            </button>
          ))}
        </nav>
      </div>

      {subTab === 'extra' ? <ExtraEventForm subTab="extra" courses={options.courses} options={options} /> : subTab === 'quiz' ? <ExtraEventForm subTab="quiz" courses={options.courses} options={options} /> : <CreatedEventsList />}
    </div>
  );
}
