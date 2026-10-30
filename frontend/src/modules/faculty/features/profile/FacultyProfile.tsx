import { Card, Badge } from '@/components/ui';
import { GraduationCap, Hash, Phone, UserRound } from 'lucide-react';
import useProfile from '@shared/hooks/useProfile';

/**
 * Faculty Profile — read-only.
 *
 * Designation and timetable notation are set at signup and arbitrated by the
 * server, so unlike the student profile there is nothing to edit here: the
 * page states what the account teaches under and what it claims to be.
 */
export default function FacultyProfile() {
  const { profile, loading } = useProfile();

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div
          className="animate-spin rounded-full border-2 border-current border-t-transparent"
          style={{ color: 'var(--cp-primary)', width: 26, height: 26 }}
        />
      </div>
    );
  }

  const name = [profile?.first_name, profile?.last_name].filter(Boolean).join(' ') || 'Faculty';
  const initials = name
    .split(' ')
    .map(part => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase();

  const rows = [
    { Icon: GraduationCap, term: 'Designation', value: profile?.designation },
    { Icon: Hash, term: 'Timetable notation', value: profile?.timetable_notation },
    { Icon: Phone, term: 'Phone', value: profile?.phone },
    { Icon: UserRound, term: 'Bio', value: profile?.bio },
  ].filter(row => row.value);

  return (
    <div className="space-y-4 max-w-2xl mx-auto">
      <Card className="text-center space-y-2">
        <div
          className="mx-auto flex items-center justify-center rounded-full font-semibold"
          style={{
            width: 64,
            height: 64,
            fontSize: 20,
            color: 'var(--cp-primary)',
            background: 'var(--cp-bg)',
            boxShadow: 'var(--cp-neu-inset)',
          }}
        >
          {initials || '?'}
        </div>
        <h2 className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
          {name}
        </h2>
        {profile?.designation && (
          <Badge tone="primary" className="inline-flex">
            {profile.designation}
          </Badge>
        )}
        {profile?.timetable_notation && (
          <p className="text-sm font-mono" style={{ color: 'var(--cp-muted)' }}>
            Notation: {profile.timetable_notation}
          </p>
        )}
      </Card>

      {rows.length > 0 && (
        <Card>
          <dl className="space-y-3 text-sm">
            {rows.map(({ Icon, term, value }) => (
              <div key={term} className="flex items-center justify-between gap-3">
                <dt className="flex items-center gap-2" style={{ color: 'var(--cp-muted)' }}>
                  <Icon size={15} strokeWidth={2} aria-hidden />
                  {term}
                </dt>
                <dd className="text-right" style={{ color: 'var(--cp-text)' }}>
                  {value}
                </dd>
              </div>
            ))}
          </dl>
        </Card>
      )}
    </div>
  );
}
