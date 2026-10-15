import type { SelectHTMLAttributes } from 'react';
export default function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`select-field ${props.className ?? ''}`} />;
}
