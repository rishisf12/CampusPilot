import { useState } from 'react';
import { Card } from '@/components/ui';
import { Plus, Clock } from 'lucide-react';
import useProfile from '@shared/hooks/useProfile';

type ManageSubTab = 'extra' | 'quiz';

const SUB_TAB_LABELS: Record<ManageSubTab, string> = {
  extra: 'Extra Class',
  quiz: 'Quiz',
};

/** Shared form for adding an extra class or quiz. */
function ExtraEventForm({
  subTab,
  courses,
}: {
  subTab: ManageSubTab;
  courses: Array<{ code: string; name: string; is_extra?: boolean }>;
}) {
  const [selectedCode, setSelectedCode] = useState('');
  const [label, setLabel] = useState(subTab === 'quiz' ? 'Quiz-1' : 'Extraclass');
  const [dateStr, setDateStr] = useState('');
  const [timeSlot, setTimeSlot] = useState('');
  const [status, setStatus] = useState<'idle' | 'ok' | 'error'>('idle');
  const [statusMsg, setStatusMsg] = useState('');

  const selectedCourse = courses.find(c => c.code === selectedCode);

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
        body: JSON.stringify({
          course_code: selectedCode,
          label,
          event_date: dateStr,
          time_slot: timeSlot,
        }),
      });
      if (!res.ok) throw new Error(`Server responded ${res.status}`);
      setStatus('ok');
      setStatusMsg(
        `${subTab === 'quiz' ? 'Quiz' : 'Extra class'} added — it now appears in Live Schedule.`
      );
      setSelectedCode('');
      setLabel(subTab === 'quiz' ? 'Quiz-1' : 'Extraclass');
      setDateStr('');
      setTimeSlot('');
    } catch {
      setStatus('error');
      setStatusMsg('Failed to add extra event. Try again.');
    }
  };

  const input = {
    className:
      'w-full rounded px-3 py-2 text-sm bg-[var(--cp-bg)] border border-[var(--cp-border)] text-[var(--cp-text)]',
  };

  return (
    <Card>
      <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--cp-text)' }}>
        {subTab === 'quiz' ? 'Add Quiz' : 'Add Extra Class'}
      </h2>
      <form onSubmit={handleSubmit} className="space-y-3">
        {/* Course dropdown */}
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>
            Course
          </label>
          <select
            value={selectedCode}
            onChange={e => setSelectedCode(e.target.value)}
            className={input.className}
          >
            <option value="">Select course</option>
            {courses.map(c => (
              <option key={c.code} value={c.code}>
                {c.code} — {c.name} {c.is_extra ? ' (Extra)' : ''}
              </option>
            ))}
          </select>
        </div>

        {/* Label input */}
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>
            Label
          </label>
          <input
            type="text"
            value={label}
            onChange={e => setLabel(e.target.value)}
            placeholder="e.g. Extraclass, Quiz-1"
            className={input.className}
          />
        </div>

        {/* Date picker */}
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>
            Date
          </label>
          <input
            type="date"
            value={dateStr}
            onChange={e => setDateStr(e.target.value)}
            className={input.className}
          />
        </div>

        {/* Time slot */}
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>
            Time slot (vacant room lookup applies)
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={timeSlot}
              onChange={e => setTimeSlot(e.target.value)}
              placeholder="e.g. Mon 09:00 — 09:55"
              className="flex-1 rounded px-3 py-2 text-sm bg-[var(--cp-bg)] border border-[var(--cp-border)] text-[var(--cp-text)]"
            />
            <button
              type="button"
              onClick={() => {
                setStatus('idle');
                setStatusMsg(
                  `Vacant room check for ${dateStr || 'no date'} at ${timeSlot || 'no time'}.`
                );
              }}
              className="rounded px-3 py-2 text-xs font-medium bg-[var(--cp-surface)] border border-[var(--cp-border)] hover:brightness-110 transition"
              style={{ color: 'var(--cp-text)' }}
            >
              <Clock size={14} /> Check vacant
            </button>
          </div>
        </div>

        <button
          type="submit"
          className="inline-flex items-center gap-2 rounded px-4 py-2 text-sm font-medium bg-[var(--cp-primary)] text-white hover:brightness-110 transition w-full md:w-auto"
        >
          <Plus size={16} /> Add {subTab === 'quiz' ? 'Quiz' : 'Extra Class'}
        </button>

        {status === 'ok' && <p className="text-sm text-emerald-600 mt-2">{statusMsg}</p>}
        {status === 'error' && <p className="text-sm text-red-600 mt-2">{statusMsg}</p>}
      </form>

      {/* Selected course info */}
      {selectedCourse && (
        <div
          className="mt-3 p-3 rounded text-xs bg-[var(--cp-surface)] border border-[var(--cp-border)]"
          style={{ color: 'var(--cp-text)' }}
        >
          Selected: <b>{selectedCourse.code}</b> — {selectedCourse.name}
          {selectedCourse.is_extra ? ' (Extra course)' : ''}
        </div>
      )}
    </Card>
  );
}

/** Faculty section manager: sub-tabs for Extra Class and Quiz. */
export default function FacultyManage() {
  const { profile } = useProfile();
  const courses = (profile?.courses || []) as Array<{
    code: string;
    name: string;
    is_extra?: boolean;
  }>;

  const [subTab, setSubTab] = useState<ManageSubTab>('extra');

  return (
    <div className="space-y-4 max-w-xl mx-auto">
      {/* Sub-tabs: Extra Class | Quiz */}
      <div className="flex gap-2 overflow-x-auto w-full max-w-xl px-2 pb-1.5">
        <nav className="flex gap-2" aria-label="Manage sub-tabs">
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
                    ? {
                        borderRadius: '0.5rem',
                        background: 'var(--cp-surface)',
                        color: 'var(--cp-primary)',
                        boxShadow: 'var(--cp-clay)',
                        border: '1px solid rgba(255,255,255,.22)',
                      }
                    : {
                        borderRadius: '0.5rem',
                        background: 'rgba(255,255,255,.06)',
                        color: 'var(--cp-text)',
                        border: '1px solid rgba(163,177,198,.3)',
                      }
                }
              >
                {SUB_TAB_LABELS[id]}
              </button>
            );
          })}
        </nav>
      </div>

      {subTab === 'extra' ? (
        <ExtraEventForm subTab="extra" courses={courses} />
      ) : (
        <ExtraEventForm subTab="quiz" courses={courses} />
      )}
    </div>
  );
}
