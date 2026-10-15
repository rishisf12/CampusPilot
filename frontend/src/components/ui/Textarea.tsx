import type { TextareaHTMLAttributes } from 'react';
export default function Textarea({
  rows = 4,
  className = '',
  style,
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      rows={rows}
      {...rest}
      className={`input-field ${className}`}
      style={{ resize: 'vertical', ...style }}
    />
  );
}
