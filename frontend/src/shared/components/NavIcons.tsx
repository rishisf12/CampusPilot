import {
  CalendarDays,
  ListTodo,
  MessageSquare,
  Plus,
  Settings as SettingsIcon,
  Sparkles,
  UserCog,
  Users,
} from 'lucide-react';

export const SECTION_ICONS: Record<string, (props: { className?: string }) => React.ReactNode> = {
  classroom: ({ className = 'w-5 h-5' }: { className?: string }) => (
    <CalendarDays className={className} strokeWidth={2} aria-hidden />
  ),
  'my-team': ({ className = 'w-5 h-5' }: { className?: string }) => (
    <Users className={className} strokeWidth={2} aria-hidden />
  ),
  feedback: ({ className = 'w-5 h-5' }: { className?: string }) => (
    <MessageSquare className={className} strokeWidth={2} aria-hidden />
  ),
  task: ({ className = 'w-5 h-5' }: { className?: string }) => (
    <ListTodo className={className} strokeWidth={2} aria-hidden />
  ),
  profile: ({ className = 'w-5 h-5' }: { className?: string }) => (
    <UserCog className={className} strokeWidth={2} aria-hidden />
  ),
  important: ({ className = 'w-5 h-5' }: { className?: string }) => (
    <Sparkles className={className} strokeWidth={2} aria-hidden />
  ),
  settings: ({ className = 'w-5 h-5' }: { className?: string }) => (
    <SettingsIcon className={className} strokeWidth={2} aria-hidden />
  ),
  manage: ({ className = 'w-5 h-5' }: { className?: string }) => (
    <Plus className={className} strokeWidth={2} aria-hidden />
  ),
};

export const SECTION_LABELS: Record<string, string> = {
  classroom: 'Classroom',
  'my-team': 'Collaborations',
  important: 'Events',
  jagrati: 'Jagrati',
  cultural: 'Cultural',
  technical: 'Technical',
  sports: 'Sports',
  feedback: 'Feedback',
  task: 'Task',
  profile: 'Profile',
  settings: 'Settings',
  manage: 'Manage',
};
