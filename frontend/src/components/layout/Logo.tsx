import Logo3D from './Logo3D';

export default function Logo({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <Logo3D size={40} />
      {!collapsed && (
        <div className="leading-tight">
          <p className="text-lg font-bold" style={{ color: 'var(--cp-text)' }}>
            essential
          </p>
          <p
            className="text-[10px] tracking-widest font-semibold"
            style={{ color: 'var(--cp-muted)' }}
          >
            IIITDMJ's CAMPUS ASSISTANT
          </p>
        </div>
      )}
    </div>
  );
}
