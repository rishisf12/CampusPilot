/**
 * Opportunities Manager — Admin view to list, filter, and transition opportunities.
 */
import { useCallback, useEffect, useState } from 'react';
import { RefreshCw, CheckCircle2, AlertTriangle } from 'lucide-react';
import { oppfeedApi } from './api';
import { Badge, Button, Card, Table } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';

export default function OpportunitiesManager({ onError }: { onError?: (m: string) => void }) {
  const [items, setItems] = useState<
    Array<{
      id: number;
      slug: string;
      title: string;
      organization_name: string;
      opportunity_type: string;
      status: string;
      confidence_score: number | null;
      source_domain: string | null;
      created_at: string | null;
    }>
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await oppfeedApi.listOpportunities({ status: statusFilter || undefined });
      setItems(data || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load opportunities');
      onError?.(err instanceof Error ? err.message : 'Failed to load opportunities');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, onError]);

  useEffect(() => {
    load();
  }, [load]);

  const transition = async (id: number, action: string) => {
    try {
      await oppfeedApi.transitionState(id, { action });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action}`);
      onError?.(err instanceof Error ? err.message : `Failed to ${action}`);
    }
  };

  if (loading) {
    return (
      <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
        Loading opportunities…
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
          Opportunities
        </h2>
        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="text-xs border rounded px-2 py-1"
            style={{ color: 'var(--cp-text)', background: 'var(--cp-bg)' }}
          >
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="in_review">In Review</option>
            <option value="approved">Approved</option>
            <option value="published">Published</option>
            <option value="rejected">Rejected</option>
            <option value="archived">Archived</option>
          </select>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            icon={<RefreshCw size={16} strokeWidth={2} aria-hidden />}
            onClick={load}
          >
            Refresh
          </Button>
        </div>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {items.length === 0 ? (
        <div className="p-3 text-center" style={{ color: 'var(--cp-muted)' }}>
          No opportunities found.
        </div>
      ) : (
        <Card>
          <Table
            head={['ID', 'Title', 'Org', 'Type', 'Status', 'Confidence', 'Source', 'Actions']}
            rows={items.map(item => [
              <span key="id" className="font-mono text-xs" style={{ color: 'var(--cp-text)' }}>
                {item.id}
              </span>,
              <span
                key="tl"
                className="text-xs font-semibold truncate"
                style={{ color: 'var(--cp-text)' }}
                title={item.title}
              >
                {item.title}
              </span>,
              <span
                key="or"
                className="text-xs truncate"
                style={{ color: 'var(--cp-muted)' }}
                title={item.organization_name}
              >
                {item.organization_name}
              </span>,
              <span key="ty" className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                {item.opportunity_type}
              </span>,
              <Badge
                key="st"
                tone={
                  item.status === 'published'
                    ? 'success'
                    : item.status === 'approved'
                      ? 'warning'
                      : item.status === 'rejected'
                        ? 'danger'
                        : item.status === 'draft'
                          ? 'neutral'
                          : 'neutral'
                }
              >
                {item.status}
              </Badge>,
              <span key="cf" className="text-xs font-mono" style={{ color: 'var(--cp-muted)' }}>
                {item.confidence_score?.toFixed(2) ?? '—'}
              </span>,
              <span
                key="sd"
                className="text-xs truncate"
                style={{ color: 'var(--cp-muted)' }}
                title={item.source_domain ?? '—'}
              >
                {item.source_domain ?? '—'}
              </span>,
              <div key="ac" className="flex items-center gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  icon={<CheckCircle2 size={14} strokeWidth={2} aria-hidden />}
                  onClick={() => transition(item.id, 'approve')}
                  disabled={item.status === 'approved'}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  icon={<AlertTriangle size={14} strokeWidth={2} aria-hidden />}
                  onClick={() => transition(item.id, 'reject')}
                  disabled={item.status === 'rejected'}
                />
              </div>,
            ])}
          />
        </Card>
      )}
    </div>
  );
}
