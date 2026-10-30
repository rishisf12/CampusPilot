import { useState } from 'react';
import { Card } from '@/components/ui';
import { Plus, Trash2 } from 'lucide-react';
import useProfile from '@shared/hooks/useProfile';

/** Faculty section manager: add extra class or quiz, linked to instructor courses. */
export default function FacultyManage() {
  const { profile } = useProfile();
  const courses = (profile?.courses || []) as Array<{code:string;name:string;is_extra?:boolean}>;

  const [selectedCode, setSelectedCode] = useState('');
  const [label, setLabel] = useState('');
  const [dateStr, setDateStr] = useState('');
  const [timeSlot, setTimeSlot] = useState('');

  const selectedCourse = courses.find((c:{code:string}) => c.code === selectedCode);

  return (
    <div className="space-y-4 max-w-xl mx-auto">
      <Card>
        <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--cp-text)' }}>
          Section Manage
        </h2>

        {/* Course dropdown */}
        <label className="block text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>Course</label>
        <select
          value={selectedCode}
          onChange={e => setSelectedCode(e.target.value)}
          className="w-full rounded px-3 py-2 text-sm bg-[var(--cp-bg)] border border-[var(--cp-border)] text-[var(--cp-text)]"
        >
          <option value="">Select course</option>
          {courses.map((c:{code:string;name:string;is_extra?:boolean}) => (
            <option key={c.code} value={c.code}>
              {c.code} — {c.name} {c.is_extra ? '(Extra)' : ''}
            </option>
          ))}
        </select>

        {/* Label input */}
        <label className="block text-sm mt-3 mb-1" style={{ color: 'var(--cp-muted)' }}>Label</label>
        <input
          type="text"
          value={label}
          onChange={e => setLabel(e.target.value)}
          placeholder="e.g. Extraclass, Quiz-1"
          className="w-full rounded px-3 py-2 text-sm bg-[var(--cp-bg)] border border-[var(--cp-border)] text-[var(--cp-text)]"
        />

        {/* Date picker */}
        <label className="block text-sm mt-3 mb-1" style={{ color: 'var(--cp-muted)' }}>Date</label>
        <input
          type="date"
          value={dateStr}
          onChange={e => setDateStr(e.target.value)}
          className="w-full rounded px-3 py-2 text-sm bg-[var(--cp-bg)] border border-[var(--cp-border)] text-[var(--cp-text)]"
        />

        {/* Time / vacant room */}
        <label className="block text-sm mt-3 mb-1" style={{ color: 'var(--cp-muted)' }}>Time slot (vacant room lookup applies)</label>
        <div className="flex gap-2">
          <input
            type="text"
            value={timeSlot}
            onChange={e => setTimeSlot(e.target.value)}
            placeholder="e.g. Mon 09:00 — 09:55"
            className="flex-1 rounded px-3 py-2 text-sm bg-[var(--cp-bg)] border border-[var(--cp-border)] text-[var(--cp-text)]"
          />
          <button
            onClick={() => alert(`Vacant room lookup for: ${dateStr || 'no date'} at ${timeSlot || 'no time'}`)}
            className="rounded px-3 py-2 text-xs font-medium bg-[var(--cp-surface)] border border-[var(--cp-border)] hover:brightness-110 transition"
            style={{ color: 'var(--cp-text)' }}
          >
            Check vacant
          </button>
        </div>

        <div className="flex gap-2 mt-4">
          <button
            onClick={() => alert(`Add extra: ${selectedCode} / ${label} / ${dateStr} / ${timeSlot}`)}
            className="inline-flex items-center gap-2 rounded px-4 py-2 text-sm font-medium bg-[var(--cp-primary)] text-white hover:brightness-110 transition"
          >
            <Plus size={16} /> Add
          </button>
          <button
            onClick={() => alert('Cancel / delete selected extra (syncs everywhere)')}
            className="inline-flex items-center gap-2 rounded px-4 py-2 text-sm font-medium bg-red-600 text-white hover:brightness-110 transition"
          >
            <Trash2 size={16} /> Cancel
          </button>
        </div>

        {/* Selected course info */}
        {selectedCourse && (
          <div className="mt-3 p-3 rounded text-xs bg-[var(--cp-surface)] border border-[var(--cp-border)]" style={{ color: 'var(--cp-text)' }}>
            Selected: <b>{selectedCourse?.code}</b> — {selectedCourse?.name}
            {selectedCourse?.is_extra ? ' (Extra course)' : ''}
          </div>
        )}
      </Card>
    </div>
  );
}
