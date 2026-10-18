/**
 * OppFeed List — Faculty view of available opportunities.
 *
 * Shows a paginated, filterable list of published opportunities with
 * cards per opportunity.
 */
import { useCallback, useEffect, useState } from 'react';
import { Calendar } from 'lucide-react';
import { oppfeedApi } from '@/api';
import { Badge, Button, Card } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';
import type { OpportunityCard } from '@/shared/types/api';

export default function OppFeedList() {
  const [items, setItems] = useState<OpportunityCard[]>([]);
  const [filters, setFilters] = useState<{
    opportunity_type?: string;
    location?: string;
    work_mode?: string;
    search?: string;
  }>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [total, setTotal] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await oppfeedApi.listFaculty({
        page,
        page_size: 20,
        ...filters,
      });
      if (page === 1) {
        setItems(data.items || []);
      } else {
        setItems(prev => [...prev, ...(data.items || [])]);
      }
      setTotal(data.total);
      setHasMore(data.has_more);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load opportunities');
    } finally {
      setLoading(false);
    }
  }, [page, filters]);

  useEffect(() => {
    load();
  }, [load]);

  const setFilter = (key: string, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value || undefined }));
    setPage(1);
  };

  if (loading) {
    return (
      <Card className="flex justify-center py-20 text-sm" style={{ color: 'var(--cp-muted)' }}>
        Loading opportunities…
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--cp-text)' }}>
            Opportunities
          </h1>
          <p className="text-sm" style={{ color: 'var(--cp-muted)' }}>
            {total} opportunity{total === 1 ? '' : 's'} available
          </p>
        </div>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={filters.opportunity_type || ''}
          onChange={e => setFilter('opportunity_type', e.target.value)}
          className="text-xs border rounded px-2 py-1"
          style={{ color: 'var(--cp-text)', background: 'var(--cp-bg)' }}
        >
          <option value="">All Types</option>
          <option value="internship">Internship</option>
          <option value="job">Job</option>
          <option value="hackathon">Hackathon</option>
          <option value="fellowship">Fellowship</option>
        </select>
        <select
          value={filters.work_mode || ''}
          onChange={e => setFilter('work_mode', e.target.value)}
          className="text-xs border rounded px-2 py-1"
          style={{ color: 'var(--cp-text)', background: 'var(--cp-bg)' }}
        >
          <option value="">All Work Modes</option>
          <option value="onsite">Onsite</option>
          <option value="remote">Remote</option>
          <option value="hybrid">Hybrid</option>
        </select>
        <input
          type="text"
          placeholder="Search title or org…"
          value={filters.search || ''}
          onChange={e => setFilter('search', e.target.value)}
          className="text-xs border rounded px-2 py-1 w-48"
          style={{ color: 'var(--cp-text)', background: 'var(--cp-bg)' }}
        />
        <Button type="button" variant="ghost" size="sm" onClick={() => load()}>
          Search
        </Button>
      </div>

      {/* Opportunity grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {items.length === 0 ? (
          <div className="col-span-3 p-6 text-center" style={{ color: 'var(--cp-muted)' }}>
            No opportunities found.
          </div>
        ) : (
          items.map(item => (
            <Card
              key={item.slug}
              className="p-3 cursor-pointer hover:neu-raised-sm transition-all duration-200"
            >
              <div className="flex items-start justify-between mb-2">
                <Badge
                  tone={
                    item.opportunity_type === 'internship'
                      ? 'info'
                      : item.opportunity_type === 'job'
                        ? 'success'
                        : item.opportunity_type === 'hackathon'
                          ? 'warning'
                          : 'neutral'
                  }
                >
                  {item.opportunity_type}
                </Badge>
                {item.work_mode && (
                  <Badge tone="neutral" className="text-xs">
                    {item.work_mode}
                  </Badge>
                )}
              </div>
              <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--cp-text)' }}>
                {item.title}
              </h3>
              <p className="text-xs text-muted-foreground mb-1 truncate">
                {item.organization_name}
              </p>
              <div className="flex items-center gap-1 mb-2">
                <span className="text-[10px]" style={{ color: 'var(--cp-muted)' }}>
                  {item.location ?? '—'}
                </span>
                {item.stipend_min && item.stipend_max && (
                  <span
                    className="text-[10px] font-semibold"
                    style={{ color: 'var(--cp-success)' }}
                  >
                    ₹{item.stipend_min}–{item.stipend_max}
                  </span>
                )}
              </div>
              <p className="text-[10px]" style={{ color: 'var(--cp-muted)' }}>
                {item.short_summary ?? 'No summary available.'}
              </p>
              {item.registration_deadline && (
                <div className="flex items-center gap-1 mt-2">
                  <Calendar size={12} strokeWidth={2} aria-hidden />
                  <span className="text-[10px]" style={{ color: 'var(--cp-muted)' }}>
                    Deadline: {new Date(item.registration_deadline).toLocaleDateString()}
                  </span>
                </div>
              )}
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="w-full mt-2"
                onClick={() => {
                  alert(`Opening ${item.title} details`);
                }}
              >
                View Details
              </Button>
            </Card>
          ))
        )}
      </div>

      {hasMore && page * 20 < total && (
        <div className="text-center">
          <Button type="button" variant="ghost" size="sm" onClick={() => setPage(page + 1)}>
            Load More
          </Button>
        </div>
      )}
    </div>
  );
}
