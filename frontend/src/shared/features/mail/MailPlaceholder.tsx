/**
 * Placeholder mounted by the Important subsection while the mail workspace
 * is being rebuilt (Phase 1 clean slate). Replaced by MailWorkspace in
 * Phase 2.
 */
function MailPlaceholder() {
  return (
    <div className="py-8 text-center" style={{ color: 'var(--cp-muted)' }}>
      <p className="text-sm">Mail workspace is being rebuilt.</p>
      <p className="mt-1 text-xs">The sender-routed webmail arrives in Phase 2.</p>
    </div>
  );
}

export default MailPlaceholder;
export { MailPlaceholder };
