/**
 * Fixed backdrop behind the sign-in screens: the blueprint dot grid plus the
 * two 45° corner washes (see .cp-tech-* and .cp-blob-* in index.css).
 *
 * Fixed, not absolute, so the washes sit behind the scrolling content instead
 * of sliding with it; z-index -1 keeps it under the auth cards.
 */
export default function TechBackground() {
  return (
    <div className="cp-tech-bg" aria-hidden="true">
      <div className="cp-tech-grid" />
      <div className="cp-blob cp-blob-a" />
      <div className="cp-blob cp-blob-b" />
      <div className="cp-blob cp-blob-c" />
    </div>
  );
}
