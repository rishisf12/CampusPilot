/**
 * The blueprint backdrop every auth page sits on.
 *
 * Three layers, cheapest first, all decorative:
 *
 *   1. a faint dot grid, so the page reads as graph paper rather than blank
 *   2. slowly drifting blurred teal blobs, which give the flat area some depth
 *   3. nothing else - no content here, ever
 *
 * Fixed and aria-hidden so it never intercepts clicks or reaches a screen
 * reader. The drift is CSS-only (`cp-drift-*` in index.css) so it stays on the
 * compositor and costs nothing per frame.
 *
 * The OS asking for reduced motion disables the drift and the shimmer. That is
 * handled by the global reduced-motion rule rather than here, so there is one
 * place that decides.
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
