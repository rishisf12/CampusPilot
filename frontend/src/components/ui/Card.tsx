import type { HTMLAttributes } from 'react';
export default function Card({ className = '', ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`neu-raised p-6 ${className}`} {...rest} />;
}
