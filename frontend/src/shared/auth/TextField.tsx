import { CheckCircle2, Eye, EyeOff, AlertCircle } from 'lucide-react';
import { useId, useState, type ReactNode } from 'react';

/**
 * One labelled input, styled the way the auth pages want it.
 *
 * The label is always rendered above the field. Not a placeholder: placeholders
 * disappear the moment the user types, which loses the label for anyone
 * returning to correct a field, and they are near-unreadable at low contrast.
 *
 * Everything optional is off by default, so a plain text field is just a
 * label plus an input.
 *
 * This component owns presentation only. It never validates - `error` and
 * `valid` are passed in - so validation stays where it already lives, in the
 * forms, and no logic moves here.
 */
interface TextFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  /** Kept as-is: ids are referenced by labels and by tests. */
  id?: string;
  name?: string;
  type?: string;
  icon?: ReactNode;
  placeholder?: string;
  autoComplete?: string;
  required?: boolean;
  error?: string | null;
  valid?: boolean;
  /** Position in the card's stagger, set by the form. */
  index?: number;
  disabled?: boolean;
}

export default function TextField({
  label,
  value,
  onChange,
  id,
  name,
  type = 'text',
  icon,
  placeholder,
  autoComplete,
  required,
  error,
  valid,
  index = 0,
  disabled,
}: TextFieldProps) {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  const errorId = `${fieldId}-error`;
  const [revealed, setRevealed] = useState(false);
  const isPassword = type === 'password';
  const inputType = isPassword && revealed ? 'text' : type;

  return (
    <div className="cp-field" style={{ ['--i' as string]: index }}>
      <div className="cp-fieldgroup">
        <label className="cp-field-label" htmlFor={fieldId}>
          {label}
        </label>
        <div className="cp-input-wrap">
          {icon && (
            <span className="contents" aria-hidden="true">
              {icon}
            </span>
          )}
          <input
            id={fieldId}
            name={name ?? fieldId}
            type={inputType}
            className={[
              'cp-input',
              icon ? 'cp-input-hasicon' : '',
              isPassword ? 'cp-input-hasreveal' : '',
              error ? 'cp-input-invalid cp-shake' : '',
              valid && !error ? 'cp-input-valid' : '',
            ]
              .filter(Boolean)
              .join(' ')}
            value={value}
            onChange={event => onChange(event.target.value)}
            placeholder={placeholder}
            autoComplete={autoComplete}
            required={required}
            disabled={disabled}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? errorId : undefined}
          />

          {isPassword && (
            <button
              type="button"
              className="cp-reveal"
              onClick={() => setRevealed(v => !v)}
              aria-pressed={revealed}
              aria-label={revealed ? `Hide ${label}` : `Show ${label}`}
            >
              <EyeOff size={17} className="cp-reveal-icon cp-reveal-icon-off" aria-hidden />
              <Eye size={17} className="cp-reveal-icon cp-reveal-icon-on" aria-hidden />
            </button>
          )}
        </div>

        {error && (
          <p className="cp-error" id={errorId} role="alert">
            <AlertCircle size={13} aria-hidden />
            {error}
          </p>
        )}
        {!error && valid && (
          <p className="cp-ok" aria-hidden="true">
            <CheckCircle2 size={13} />
          </p>
        )}
      </div>
    </div>
  );
}
