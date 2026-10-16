import {
  Activity,
  AlertCircle,
  CalendarDays,
  MessageSquare,
  Settings as SettingsIcon,
  UserCog,
  Users,
} from 'lucide-react';

export const SECTION_ICONS = {
  classroom: ({ className = 'w-5 h-5' }: { className?: string }) => (
    <CalendarDays className={className} strokeWidth={2} aria-hidden />
  ),
  'my-team': ({ className = 'w-5 h-5' }: { className?: string }) => (
    <Users className={className} strokeWidth={2} aria-hidden />
  ),
  feedback: ({ className = 'w-5 h-5' }: { className?: string }) => (
    <MessageSquare className={className} strokeWidth={2} aria-hidden />
  ),
  profile: ({ className = 'w-5 h-5' }: { className?: string }) => (
    <UserCog className={className} strokeWidth={2} aria-hidden />
  ),
  monitoring: ({ className = 'w-5 h-5' }: { className?: string }) => (
    <Activity className={className} strokeWidth={2} aria-hidden />
  ),
  important: ({ className = 'w-5 h-5' }: { className?: string }) => (
    <AlertCircle className={className} strokeWidth={2} aria-hidden />
  ),
  settings: ({ className = 'w-5 h-5' }: { className?: string }) => (
    <SettingsIcon className={className} strokeWidth={2} aria-hidden />
  ),
};

export const SECTION_LABELS: Record<string, string> = {
  classroom: 'Classroom',
  'my-team': 'Collaborations',
  important: 'Important',
  feedback: 'Feedback',
  profile: 'Profile',
  settings: 'Settings',
};
