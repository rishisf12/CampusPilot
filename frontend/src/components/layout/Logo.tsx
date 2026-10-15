import { GraduationCap } from 'lucide-react';
import IconTile from '../ui/IconTile';

export default function Logo({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <IconTile hue="indigo" size={40}>
        <GraduationCap size={22} strokeWidth={2} aria-hidden />
      </IconTile>
      {!collapsed && (
        <div className="leading-tight">
          <p className="text-lg font-bold" style={{ color: 'var(--cp-text)' }}>
            essential
          </p>
          <p
            className="text-[10px] tracking-widest font-semibold"
            style={{ color: 'var(--cp-muted)' }}
          >
            YOUR CAMPUS ASSISTANT
          </p>
        </div>
      )}
    </div>
  );
}
