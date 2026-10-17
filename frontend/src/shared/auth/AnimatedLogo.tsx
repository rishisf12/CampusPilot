/**
 * The mark, rebuilt as something that can move.
 *
 * Geometry is taken from `public/logo-icon.svg` so the animated version is
 * recognisably the same logo: a stroked ring, a clock face reading 9 / 11 / 2,
 * an open grin, and the body below. What is new is the movement:
 *
 *   - the ring draws itself once on mount, via stroke-dashoffset
 *   - the eyes blink on their own cycle
 *   - the whole mark floats with a soft glow
 *
 * The waving hand is opt-in (`hand`). The landing screen drops it in for its
 * intro; every other page keeps the plain mark.
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

/** Interior of the open grin, and the tongue inside it. */
const MOUTH = '#334155';
const TONGUE = '#e2564f';

/** The waving hand - a soft yellow glove with a darker cuff. Fixed rather than
 *  themed: a glove stays yellow in either theme. */
const GLOVE = '#ffd966';
const GLOVE_CUFF = '#b8860b';

interface AnimatedLogoProps {
  /** Rendered size in px. Pages with a form pass a smaller box. */
  size?: number;
  /** Text alternative. The mark is decorative next to a visible wordmark. */
  title?: string;
  /** Show the waving hand. Off by default so only the landing screen gets it. */
  hand?: boolean;
}

export default function AnimatedLogo({
  size = 64,
  title = 'Essential',
  hand = false,
}: AnimatedLogoProps) {
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

        {/* Clips the teeth and tongue to the grin, so they can never spill
            outside the mouth outline. Same shape as the interior path. */}
        <clipPath id="cp-logo-mouth">
          <path d="M-20 11 Q0 19 20 11 Q0 51 -20 11 Z" />
        </clipPath>
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

        {/* Waving hand - a soft yellow glove. Only the landing screen asks for it
            (`hand`); every other page keeps the plain mark. Drawn after the
            ring so it reads as sitting in front of the face, like the
            reference. The movement lives in index.css (.cp-logo-hand). */}
        {hand && (
          <g transform="translate(-74 6)" aria-hidden="true">
            {/* Nudge the geometry about its own centre so it sits larger. */}
            <g transform="translate(21 19) scale(1.5) translate(-21 -19)">
              <g className="cp-logo-hand" fill={GLOVE}>
                {/* Fingers - rounded so the silhouette stays soft. */}
                <rect x="2" y="-6" width="6" height="28" rx="3" />
                <rect x="9.5" y="-12" width="6" height="34" rx="3" />
                <rect x="17" y="-8" width="6" height="30" rx="3" />
                <rect x="24" y="-3" width="6" height="25" rx="3" />
                {/* Thumb, angled in toward the face. */}
                <rect
                  x="27"
                  y="25"
                  width="15"
                  height="7.5"
                  rx="3.75"
                  transform="rotate(-20 27 28.75)"
                />
                {/* Palm, then the cuff band across the wrist in the darker
                    yellow, drawn last so it reads as the glove's trim. */}
                <rect x="0" y="16" width="33" height="28" rx="14" />
                <rect x="2" y="39" width="29" height="10" rx="5" fill={GLOVE_CUFF} />
              </g>
            </g>
          </g>
        )}

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

          {/* Open grin, matching the reference: a dark interior, a white row of
              top teeth, and a tongue. Clipped to the grin outline. */}
          <g className="cp-logo-smile" clipPath="url(#cp-logo-mouth)">
            <path d="M-20 11 Q0 19 20 11 Q0 51 -20 11 Z" fill={MOUTH} />
            <path d="M-16.5 11.5 Q0 18.5 16.5 11.5 L16.5 15 Q0 22 -16.5 15 Z" fill="#FFFFFF" />
            <ellipse cx="0" cy="27.5" rx="8.5" ry="5.5" fill={TONGUE} />
          </g>
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
