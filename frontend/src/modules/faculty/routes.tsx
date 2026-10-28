/**
 * Faculty Routes — student-mirrored layout: header top row, centred main nav
 * with classroom / important / feedback, and an empty content area per
 * section. OppFeed removed entirely; nothing else remains.
 */
import { useState } from 'react';
import { Sidebar } from '@/shared/components/Sidebar';
import { HeaderTopRow } from '@/components/layout/HeaderTopRow';
import { CalendarDays, AlertCircle, MessageSquare } from 'lucide-react';

const FACULTY_SECTIONS = [
  { id: 'classroom', label: 'Classroom', Icon: CalendarDays },
  { id: 'important', label: 'Important', Icon: AlertCircle },
  { id: 'feedback', label: 'Feedback', Icon: MessageSquare },
] as const;

interface FacultyRoutesProps {
  online?: boolean;
}

export function FacultyRoutes({ online = true }: FacultyRoutesProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [section, setSection] = useState('classroom');

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--cp-wall)' }}>
      {/* Header flush to top and side edges, same as student. */}
      <HeaderTopRow
        online={online}
        sidebarOpen={sidebarOpen}
        onMenu={() => setSidebarOpen(!sidebarOpen)}
      />

      {/* Main navigation bar — centred, compact width, same card-style links as student. */}
      <div className="flex justify-center">
        <nav
          className="flex gap-2 overflow-x-auto w-full max-w-2xl pt-1.5 pb-1.5 px-2"
          aria-label="Main sections"
        >
          {FACULTY_SECTIONS.map(item => {
            const isActive = section === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setSection(item.id)}
                aria-current={isActive ? 'page' : undefined}
                className="inline-flex items-center justify-center gap-2 px-3 py-1.5 text-sm font-medium whitespace-nowrap flex-1 min-w-max rounded-lg transition-all duration-200"
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
                <item.Icon className="w-4 h-4" strokeWidth={2} aria-hidden />
                {item.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Empty content area per section — same padding as student main content. */}
      <main className="flex-1 min-w-0 px-3 pt-2 pb-20">
        <section
          className="neu-raised p-6"
          style={{ display: section === 'classroom' ? 'block' : 'none', color: 'var(--cp-text)' }}
        >
          <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--cp-primary)' }}>
            Classroom
          </h2>
          <p className="text-sm" style={{ color: 'var(--cp-muted)' }}>
            No classes right now.
          </p>
        </section>
        <section
          className="neu-raised p-6"
          style={{ display: section === 'important' ? 'block' : 'none', color: 'var(--cp-text)' }}
        >
          <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--cp-primary)' }}>
            Important
          </h2>
          <p className="text-sm" style={{ color: 'var(--cp-muted)' }}>
            No announcements right now.
          </p>
        </section>
        <section
          className="neu-raised p-6"
          style={{ display: section === 'feedback' ? 'block' : 'none', color: 'var(--cp-text)' }}
        >
          <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--cp-primary)' }}>
            Feedback
          </h2>
          <p className="text-sm" style={{ color: 'var(--cp-muted)' }}>
            No feedback items right now.
          </p>
        </section>
      </main>

      {/* Footer: simple text only, same as student desktop. */}
      <footer className="py-4 px-3 text-center text-xs" style={{ color: 'var(--cp-muted)' }}>
        essential &mdash; your campus assistant
      </footer>

      {/* Right-side toggle drawer: user profile, settings, logout. */}
      {sidebarOpen && (
        <Sidebar
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          onSectionChange={setSection}
        />
      )}
    </div>
  );
}
