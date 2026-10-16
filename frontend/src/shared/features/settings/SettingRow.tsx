import Toggle from '@/components/ui/Toggle';
import type { SettingsEntry, SettingsValue } from '@shared/constants';
import { useSettings } from './SettingsProvider';

/**
 * One setting, rendered from its registry entry.
 *
 * The registry decides the control: a boolean gets a switch, a choice gets a
 * radio row. That is what keeps a new setting to a single registry entry instead
 * of a new component, and it stops the label, the help text and the control from
 * drifting apart as they did when each screen hand-rolled its own row.
 */

interface SettingRowProps {
  entry: SettingsEntry;
}

export default function SettingRow({ entry }: SettingRowProps) {
  const settings = useSettings();
  const value = settings.get(entry.key);
  const pending = entry.store === 'server';

  return (
    <div
      className="flex items-start gap-4 py-3.5"
      style={{ borderBottom: '1px solid rgba(163,177,198,.18)' }}
    >
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium" style={{ color: 'var(--cp-text)' }}>
          {entry.label}
        </p>
        <p className="text-xs mt-0.5" style={{ color: 'var(--cp-muted)' }}>
          {entry.help}
        </p>
        {pending && (
          <p
            className="text-[11px] mt-1 inline-block px-2 py-0.5 rounded-full"
            style={{ background: 'var(--cp-bg)', color: 'var(--cp-muted)' }}
          >
            Saved to your account in the next update
          </p>
        )}
      </div>

      <div className="shrink-0 pt-0.5">
        <Control entry={entry} value={value} onChange={next => settings.set(entry.key, next)} />
      </div>
    </div>
  );
}

function Control({
  entry,
  value,
  onChange,
}: {
  entry: SettingsEntry;
  value: SettingsValue;
  onChange: (next: SettingsValue) => void;
}) {
  if (entry.type === 'boolean') {
    const on = value === true;
    return <Toggle checked={on} aria-label={entry.label} onClick={() => onChange(!on)} />;
  }

  if (entry.type === 'choice') {
    return (
      <div
        className="flex items-center gap-1 p-1 rounded-full"
        style={{ background: 'var(--cp-bg)', boxShadow: 'var(--cp-neu-inset)' }}
        role="radiogroup"
        aria-label={entry.label}
      >
        {entry.choices?.map(choice => {
          const active = choice.value === value;
          return (
            <button
              key={choice.value}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange(choice.value)}
              className="px-3 py-1.5 text-xs font-medium rounded-full transition-all duration-200 whitespace-nowrap"
              style={
                active
                  ? {
                      background: 'var(--cp-primary)',
                      color: 'var(--cp-on-primary)',
                      boxShadow: 'var(--cp-clay)',
                    }
                  : { color: 'var(--cp-muted)' }
              }
            >
              {choice.label}
            </button>
          );
        })}
      </div>
    );
  }

  if (entry.type === 'number') {
    return (
      <input
        type="number"
        aria-label={entry.label}
        value={typeof value === 'number' ? value : ''}
        onChange={e => onChange(Number(e.target.value))}
        className="w-24 px-3 py-2 text-sm rounded-xl"
        style={{
          background: 'var(--cp-bg)',
          color: 'var(--cp-text)',
          boxShadow: 'var(--cp-neu-inset)',
          border: '1px solid rgba(163,177,198,.3)',
        }}
      />
    );
  }

  return (
    <input
      type="text"
      aria-label={entry.label}
      value={typeof value === 'string' ? value : ''}
      onChange={e => onChange(e.target.value)}
      className="w-48 px-3 py-2 text-sm rounded-xl"
      style={{
        background: 'var(--cp-bg)',
        color: 'var(--cp-text)',
        boxShadow: 'var(--cp-neu-inset)',
        border: '1px solid rgba(163,177,198,.3)',
      }}
    />
  );
}
