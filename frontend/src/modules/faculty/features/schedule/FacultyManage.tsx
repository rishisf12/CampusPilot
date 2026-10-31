import { useState } from 'react';
import { Card } from '@/components/ui';
import { Plus, Clock } from 'lucide-react';
import useProfile from '@shared/hooks/useProfile';

type ManageSubTab = 'extra' | 'quiz';

const SUB_TAB_LABELS: Record<ManageSubTab, string> = {
  extra: 'Extra Class',
  quiz: 'Quiz',
};

/** College hours 09:00-17:00. */
const HOURS = Array.from({ length: 9 }, (_, i) => i + 9); // 9..17
const MINUTES = Array.from({ length: 60 }, (_, i) => i); // 0..59

const pad = (n: number) => n.toString().padStart(2, '0');

/** Custom dropdown time picker: hours column + minutes column, opens on click. */
function TimePicker({
  value,
  onChange,
  onVacantCheck,
}: {
  value: string; // "HH:mm"
  onChange: (v: string) => void;
  onVacantCheck: (date: string, time: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [hour, setHour] = useState<number | null>(value ? Number(value.split(':')[0]) : null);
  const [minute, setMinute] = useState<number | null>(value ? Number(value.split(':')[1]) : null);

  const formatted = hour != null && minute != null ? `${pad(hour)}:${pad(minute)}` : '';

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
                {/* Hours column */}
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-[var(--cp-muted)] mb-1">Hour</span>
                  {HOURS.map(h => (
                    <button
                      key={h}
                      type="button"
                      onClick={() => {
                        setHour(h);
                        if (minute != null) onChange(`${pad(h)}:${pad(minute)}`);
                        setOpen(false);
                      }}
                      className={`w-8 h-8 rounded text-sm font-medium ${
                        hour === h
                          ? 'bg-[var(--cp-primary)] text-white'
                          : 'text-[var(--cp-text)] hover:bg-[var(--cp-surface)]'
                      }`}
                    >
                      {pad(h)}
                    </button>
                  ))}
                </div>
                {/* Minutes column */}
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-[var(--cp-muted)] mb-1">Minute</span>
                  {MINUTES.map(m => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => {
                        setMinute(m);
                        if (hour != null) onChange(`${pad(hour)}:${pad(m)}`);
                        setOpen(false);
                      }}
                      className={`w-8 h-8 rounded text-sm font-medium ${
                        minute === m
                          ? 'bg-[var(--cp-primary)] text-white'
                          : 'text-[var(--cp-text)] hover:bg-[var(--cp-surface)]'
                      }`}
                    >
                      {pad(m)}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
        <button
          type="button"
          className="rounded px-3 py-2 text-xs font-medium bg-[var(--cp-surface)] border border-[var(--cp-border)] hover:brightness-110 transition"
          style={{ color: 'var(--cp-text)' }}
          onClick={() => onVacantCheck('', formatted)}
        >
          <Clock size={14} /> Check vacant
        </button>
      </div>
    </div>
  );
}

/** Shared form for adding an extra class or quiz. */
function ExtraEventForm({
  subTab,
  courses,
  onVacantCheck,
}: {
  subTab: ManageSubTab;
  courses: Array<{ code: string; name: string; is_extra?: boolean }>;
  onVacantCheck: (date: string, time: string) => void;
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

        {/* Time slot - custom dropdown picker matching Vacant Room Lookup */}
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>
            Time slot (vacant room lookup applies)
          </label>
          <div className="flex gap-2">
            <TimePicker value={timeSlot} onChange={setTimeSlot} onVacantCheck={onVacantCheck} />
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

  const onVacantCheck = (date: string, time: string) => {
    // Vacant room lookup is delegated to the shared VacantRoomLookup screen;
    // the time picker just captures the selected time here.

    console.log('Vacant check requested for', date, time);
  };

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
        <ExtraEventForm subTab="extra" courses={courses} onVacantCheck={onVacantCheck} />
      ) : (
        <ExtraEventForm subTab="quiz" courses={courses} onVacantCheck={onVacantCheck} />
      )}
    </div>
  );
}
