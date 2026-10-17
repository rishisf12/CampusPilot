/**
 * The mark, rebuilt as something that can move.
 *
 * Geometry is taken from `public/logo-icon.svg` so the animated version is
 * recognisably the same logo: a stroked ring, a clock face reading 9 / 11 / 2,
 * a smile, and the body below. What is new is the movement:
 *
 *   - the ring draws itself once on mount, via stroke-dashoffset
 *   - the eyes blink on their own cycle
 *   - the whole mark floats, and carries a soft glow
 *
 * Inline SVG rather than the <img>, because an <img> cannot be animated from
 * the outside. The file stays where it is for the favicon and for anything
 * that needs a static image.
 *
 * The numbers are drawn with <text> in JetBrains Mono, which is why index.html
 * loads that font. If it ever fails to load the fallback is a generic
 * monospace and the logo still reads.
 *
 * All timing lives in index.css. `size` only changes the rendered box - the
 * smaller value is what the form pages pass so the card gets the focus.
 */
interface AnimatedLogoProps {
  /** Rendered size in px. Pages with a form pass a smaller box. */
  size?: number;
  /** Text alternative. The mark is decorative next to a visible wordmark. */
  title?: string;
}

export default function AnimatedLogo({ size = 64, title = 'Essential' }: AnimatedLogoProps) {
  return (
    <svg
      width={size}
      height={(size * 165) / 170}
      viewBox="255 45 170 165"
      role="img"
      aria-label={title}
      className="cp-logo mx-auto block"
    >
      <defs>
        {/* Blur on the glow only, so the ring and the clock stay crisp. */}
        <filter id="cp-logo-glow" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="6" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <g transform="translate(340,135)">
        {/* Glow sits behind everything and fades in after the ring is drawn. */}
        <circle
          className="cp-logo-glow"
          cx="0"
          cy="-10"
          r="55"
          fill="none"
          stroke="var(--cp-primary)"
          strokeWidth="10"
          filter="url(#cp-logo-glow)"
        />

        {/* The ring: same geometry as the static file, drawn on mount.
            pathLength=100 normalises the dash maths, so the CSS works in
            percentages regardless of the real circumference. */}
        <circle
          className="cp-logo-ring"
          cx="0"
          cy="-10"
          r="55"
          fill="none"
          stroke="var(--cp-primary)"
          strokeWidth="10"
          pathLength="100"
        />

        {/* The clock numerals. aria-hidden because the whole svg is already a
            role="img" with a label, so these are presentational - without it
            they can still surface in some DOM-to-text paths. */}
        <g transform="translate(0, -12)" aria-hidden="true">
          {/* Eyes blink by scaling each group, so one transform covers both the
              circle and its numeral. */}
          <g className="cp-logo-eye">
            <circle cx="-22" cy="-8" r="10" fill="none" stroke="#475569" strokeWidth="5" />
            <text x="-22" y="-4" textAnchor="middle" className="cp-logo-num" fill="#475569">
              9
            </text>
          </g>

          <g className="cp-logo-eye cp-logo-eye-mid">
            <circle cx="0" cy="-4" r="12" fill="var(--cp-primary)" />
            <text x="0" y="0" textAnchor="middle" className="cp-logo-num" fill="#FFFFFF">
              11
            </text>
          </g>

          <g className="cp-logo-eye">
            <circle cx="22" cy="-8" r="10" fill="none" stroke="#475569" strokeWidth="5" />
            <text x="22" y="-4" textAnchor="middle" className="cp-logo-num" fill="#475569">
              2
            </text>
          </g>

          <path
            d="M-16 12 Q0 24 16 12"
            stroke="var(--cp-primary)"
            strokeWidth="5.5"
            fill="none"
            strokeLinecap="round"
            opacity="0.95"
            className="cp-logo-smile"
          />
        </g>

        <path
          d="M-20 35 L-12 50 L12 50 L20 35 Z"
          fill="var(--cp-primary)"
          className="cp-logo-body"
        />
        <rect
          x="-8"
          y="52"
          width="16"
          height="6"
          rx="3"
          fill="var(--cp-primary)"
          className="cp-logo-body"
        />
      </g>
    </svg>
  );
}
