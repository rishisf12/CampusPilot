/**
 * The wordmark: "essential" revealed a letter at a time, over a gradient shimmer.
 *
 * Each letter is its own inline-block span with a staggered animation-delay set
 * in CSS, which is what produces the cascade. Splitting into spans rather than
 * animating a single block means the letters can also each take a slice of the
 * gradient - the shimmer travels across the word instead of one flat wash.
 *
 * The tagline is the micro-label style used throughout the auth pages: monospace,
 * wide tracking, muted.
 *
 * Screen readers get the plain word. Splitting "essential" into eight spans
 * would otherwise be announced letter by letter, so the visual is hidden and an
 * aria-label carries the real string.
 *
 * `scale` exists because the form pages want the lockup a size down so the card
 * is the focus. It is a multiplier rather than px so callers do not have to know
 * the base size.
 */
interface AnimatedTitleProps {
  /** Multiplier on the base lockup. 1 = the role screen's size. */
  scale?: number;
}

const WORD = 'essential';

export default function AnimatedTitle({ scale = 1 }: AnimatedTitleProps) {
  return (
    <div
      className="text-center"
      style={{ transform: `scale(${scale})`, transformOrigin: 'center' }}
    >
      <h1 className="cp-title font-bold" style={{ fontSize: `${1.5 * scale}rem` }}>
        {WORD.split('').map((letter, index) => (
          <span
            key={`${letter}-${index}`}
            className="cp-letter"
            style={{ ['--i' as string]: index }}
          >
            {letter}
          </span>
        ))}
      </h1>
      <p className="cp-tagline mt-1">IIITDMJ's CAMPUS ASSISTANT</p>
    </div>
  );
}
