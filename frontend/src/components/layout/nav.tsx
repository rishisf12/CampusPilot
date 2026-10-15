import {
  Activity,
  CalendarDays,
  CheckCircle2,
  DoorOpen,
  FileText,
  LayoutDashboard,
  MessageSquare,
  UserCog,
  Users,
} from 'lucide-react';
import type { ReactNode } from 'react';

export interface NavItem {
  id: string;
  label: string;
  icon: ReactNode;
  hue: 'indigo' | 'mint' | 'amber' | 'coral' | 'sky' | 'slate';
}

export const CATEGORY_NAV: NavItem[] = [
  {
    id: 'classroom',
    label: 'Classroom',
    icon: <CalendarDays size={18} strokeWidth={2} aria-hidden />,
    hue: 'indigo',
  },
  {
    id: 'attendance',
    label: 'Attendance',
    icon: <CheckCircle2 size={18} strokeWidth={2} aria-hidden />,
    hue: 'mint',
  },
  {
    id: 'vacant',
    label: 'Rooms',
    icon: <DoorOpen size={18} strokeWidth={2} aria-hidden />,
    hue: 'sky',
  },
  {
    id: 'exam',
    label: 'Exam',
    icon: <FileText size={18} strokeWidth={2} aria-hidden />,
    hue: 'amber',
  },
  {
    id: 'my-team',
    label: 'Collaborations',
    icon: <Users size={18} strokeWidth={2} aria-hidden />,
    hue: 'indigo',
  },
  {
    id: 'feedback',
    label: 'Feedback',
    icon: <MessageSquare size={18} strokeWidth={2} aria-hidden />,
    hue: 'coral',
  },
  {
    id: 'monitoring',
    label: 'Monitoring',
    icon: <Activity size={18} strokeWidth={2} aria-hidden />,
    hue: 'sky',
  },
  {
    id: 'admin',
    label: 'Admin Panel',
    icon: <LayoutDashboard size={18} strokeWidth={2} aria-hidden />,
    hue: 'indigo',
  },
  {
    id: 'profile',
    label: 'Profile',
    icon: <UserCog size={18} strokeWidth={2} aria-hidden />,
    hue: 'slate',
  },
];
