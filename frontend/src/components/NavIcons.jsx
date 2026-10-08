/**
 * Nav icons for the main sections.
 *
 * Each one has to be recognisable on its own, with no text beside it, and should
 * not read as a generic stock glyph. Two of them are built from the brand
 * mark in `public/logo-icon.svg` - the bulb with the smiling face - so the nav
 * carries the same identity as the logo instead of borrowing icons out of every
 * other dashboard.
 *
 *   Classroom - the bulb itself, which is what the app is *for*. The "9 11 2"
 *               in the logo's eyes is dropped: three digits turn to mud at 48px
 *               and the face carries the idea on its own.
 *   Feedback  - that same face inside a speech bubble, so "a note from you" is
 *               tied to the brand rather than to a generic envelope.
 *   My Team   - three heads, the middle one larger: a group, not a pair.
 *   Profile   - a person silhouette with a small gear, distinct from the team
 *               heads and clearly "my settings".
 *
 * `currentColor` is the whole theming story, so a button only has to change its
 * text colour to restyle its icon.
 *
 * Inline rather than separate files: four icons on every page load does not
 * justify four requests.
 */

/** Classroom: the brand bulb. */
export function ClassroomIcon({ className = 'w-12 h-12' }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <g fill="currentColor">
        {/* Eyes. */}
        <circle cx="9.4" cy="9" r="1.45" />
        <circle cx="14.6" cy="9" r="1.45" />
        {/* Base: the tapered neck, then the contact. */}
        <path d="M9.7 16.8h4.6l-.8 3.1h-3Z" />
        <rect x="10.7" y="20.2" width="2.6" height="1.3" rx="0.65" />
      </g>
      <g fill="none" stroke="currentColor" strokeLinecap="round">
        {/* Glass. */}
        <circle cx="12" cy="9.6" r="7.6" strokeWidth="1.7" />
        {/* Smile. */}
        <path d="M8.8 12.6q3.2 3 6.4 0" strokeWidth="1.6" />
      </g>
    </svg>
  )
}

/** My Team: three heads, the middle one larger - a group, not a pair. */
export function MyTeamIcon({ className = 'w-12 h-12' }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      {/* Leader, front and centre. */}
      <circle cx="12" cy="7.9" r="4.1" />
      <path d="M12 13.4c-4.15 0-7.6 2.4-7.6 5.35 0 .92.79 1.65 1.7 1.65h11.8c.91 0 1.7-.73 1.7-1.65 0-2.95-3.45-5.35-7.6-5.35Z" />
      {/* Two behind, tucked left and right. */}
      <circle cx="4.3" cy="9.4" r="2.85" />
      <circle cx="19.7" cy="9.4" r="2.85" />
      <path d="M3.9 13.55c-1.62.62-2.7 1.75-2.7 3.02 0 .83.72 1.43 1.6 1.43h3.42c-.36-.72-.56-1.55-.56-2.42 0-1.02.3-1.97.84-2.78-.83-.17-1.72-.25-2.6-.25Z" />
      <path d="M20.1 13.55c1.62.62 2.7 1.75 2.7 3.02 0 .83-.72 1.43-1.6 1.43h-3.42c.36-.72.56-1.55.56-2.42 0-1.02-.3-1.97-.84-2.78.83-.17 1.72-.25 2.6-.25Z" />
    </svg>
  )
}

/**
 * Feedback: three faces inside a triangle made entirely of arcs.
 *
 * Two circles side by side read as a body part, and drawing a separate triangle
 * around three faces does not fit - the enclosing triangle caps the faces at
 * about 13px at nav size. Drawing a triangle *of arcs* solves both: the boundary
 * is three circular arcs, each struck at radius s about one vertex of an
 * equilateral triangle and bulging away from it. That is the Reuleaux
 * construction - no straight edge anywhere, and the three arcs meet at sharp
 * 60 degree corners, so the silhouette still reads as a triangle.
 *
 * Because the boundary is arcs and not per-face heads, each face is just two
 * eyes and a mouth, which is what leaves them room to stay large.
 *
 * Geometry, side s = 20, centroid at (12, 12): the circumradius is s/sqrt(3) =
 * 11.547, so the top vertex sits at y = 0.45 and the lower pair at y = 17.77.
 * Total height is 0.577s + 0.423s = s, which caps s at 20.8.
 *
 * All three arcs are sweep-flag 0. Each is a 60 degree span and, measured about
 * its own centre, runs from a higher atan2 angle to a lower one.
 */

//: Side length of the equilateral triangle the arcs are struck from.
const TRI_S = 20
const TRI_CIRCUM = TRI_S / Math.sqrt(3)      // 11.547
const V_TOP = [12, 12 - TRI_CIRCUM]           // 12, 0.453
const V_BL = [12 - TRI_S / 2, 12 + TRI_CIRCUM / 2]   // 2, 17.773
const V_BR = [12 + TRI_S / 2, 12 + TRI_CIRCUM / 2]   // 22, 17.773

//: Side of the equilateral triangle the three faces sit on. This is the number
//: the centre ring is sized against, and it is a compromise between two pulls
//: that fight each other: the ring needs the faces pushed out, the border needs
//: them pulled in. At 11.2 both clearances stay positive (ring 0.31, border
//: 0.33); pushing to 11.5 costs border clearance down to 0.20, and pulling in
//: to 11.0 puts the ring's arc ends through the eyes.
const FACE_TRIAD_SIDE = 11.2

//: The centre ring, drawn as three arcs rather than a closed circle so it reads
//: as three separate voices. r = 3.0 with a 1.4 stroke; the gaps are centred on
//: the faces and span 52 degrees, which is both wider than the stroke can bridge
//: and wide enough that the arcs sit in the channels between faces.
const RING_R = 3.0
const RING_SW = 1.4
const RING_GAP_HALF = 26          // half-gap, so 52 degree gaps
const RING_HALF_SPAN = 60 - RING_GAP_HALF

/** Screen degrees to a point on a circle about the icon centre. */
function polar(deg, r) {
  const a = (deg * Math.PI) / 180
  return [12 + r * Math.cos(a), 12 + r * Math.sin(a)]
}

/** One arc segment of the centre ring, as a path. */
function ringArc(centreDeg) {
  const [x0, y0] = polar(centreDeg - RING_HALF_SPAN, RING_R)
  const [x1, y1] = polar(centreDeg + RING_HALF_SPAN, RING_R)
  // Degrees increase clockwise in SVG's y-down space, and a single span here is
  // always under 180 degrees, so sweep-flag 0 is the short way round.
  return `M${x0.toFixed(2)} ${y0.toFixed(2)}A${RING_R} ${RING_R} 0 0 0 ` +
    `${x1.toFixed(2)} ${y1.toFixed(2)}`
}

/** One face: two eyes and a mouth. No head - the arcs do the enclosing. */
function Face({ cx, cy, mouth }) {
  return (
    <>
      <g fill="currentColor">
        <circle cx={cx - 1.7} cy={cy - 1.4} r="0.85" />
        <circle cx={cx + 1.7} cy={cy - 1.4} r="0.85" />
      </g>
      <g fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round">
        {mouth === 'sad' && <path d={`M${cx - 1.7} ${cy + 2.3}q1.7 -1.7 3.4 0`} />}
        {mouth === 'flat' && <path d={`M${cx - 1.7} ${cy + 1.7}h3.4`} />}
        {mouth === 'happy' && <path d={`M${cx - 1.7} ${cy + 1.1}q1.7 1.9 3.4 0`} />}
      </g>
    </>
  )
}

export function FeedbackIcon({ className = 'w-12 h-12' }) {
  const arc = (from, to) =>
    `M${from[0].toFixed(2)} ${from[1].toFixed(2)}A${TRI_S} ${TRI_S} 0 0 0 ` +
    `${to[0].toFixed(2)} ${to[1].toFixed(2)}`
  const boundary = `${arc(V_BL, V_BR)}${arc(V_BR, V_TOP)}${arc(V_TOP, V_BL)}`

  const inner = FACE_TRIAD_SIDE
  const inCircum = inner / Math.sqrt(3)
  const fTop = [12, 12 - inCircum]
  const fBl = [12 - inner / 2, 12 + inCircum / 2]
  const fBr = [12 + inner / 2, 12 + inCircum / 2]

  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path
        d={boundary}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
      {/* The centre ring, in three arcs with the gaps opening onto the faces, so
          it separates them rather than closing over them. Centred at 90, 210 and
          330 degrees - the channels between the faces at 30, 150 and 270. */}
      <path
        d={`${ringArc(90)}${ringArc(210)}${ringArc(330)}`}
        fill="none"
        stroke="currentColor"
        strokeWidth={RING_SW}
        strokeLinecap="round"
      />
      <Face cx={fTop[0]} cy={fTop[1]} mouth="flat" />
      <Face cx={fBl[0]} cy={fBl[1]} mouth="sad" />
      <Face cx={fBr[0]} cy={fBr[1]} mouth="happy" />
    </svg>
  )
}

/** Profile: a person silhouette with a small gear - "my settings". */
export function ProfileIcon({ className = 'w-12 h-12' }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      {/* Person silhouette */}
      <circle cx="12" cy="7.5" r="3.5" />
      <path d="M12 15.5c-4.42 0-8 2.55-8 5.7V21h16v-1.8c0-3.15-3.58-5.7-8-5.7Z" />
      {/* Small gear at bottom-right */}
      <g fill="currentColor" transform="translate(16.5, 16.5) scale(0.45)">
        <circle cx="0" cy="0" r="3" />
        <path d="M-3 0h-2M3 0h2M0-3v-2M0 3v2M-2.12-2.12l-1.41-1.41M2.12 2.12l1.41 1.41M-2.12 2.12l-1.41 1.41M2.12-2.12l1.41-1.41" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </g>
    </svg>
  )
}

/** Section id -> icon, so App.jsx can stay a plain map over its section list. */
export const SECTION_ICONS = {
  classroom: ClassroomIcon,
  'my-team': MyTeamIcon,
  feedback: FeedbackIcon,
  profile: ProfileIcon,
}

/** Section id -> label, kept for tooltips and accessible names. */
export const SECTION_LABELS = {
  classroom: 'Classroom',
  'my-team': 'My Team',
  feedback: 'Feedback',
  profile: 'Profile',
}