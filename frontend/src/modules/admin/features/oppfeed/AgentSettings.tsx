/**
 * Agent Settings — Admin view to configure OppFeed agent behavior.
 */
import { useCallback, useEffect, useState } from 'react';
import { oppfeedApi } from './api';
import { Button, Card, Input } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';

export default function AgentSettings({ onError }: { onError?: (m: string) => void }) {
  const [settings, setSettings] = useState<{
    run_window_start: string;
    run_window_end: string;
    auto_publish_enabled: boolean;
    auto_publish_threshold: number;
    llm_provider_chain: string;
    llm_max_rpm: number;
    max_drafts_per_run: number;
    enable_agent: boolean;
    enable_scheduler: boolean;
    enable_vision: boolean;
    enable_banner_gen: boolean;
    enable_audio_summary: boolean;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await oppfeedApi.getSettings();
      setSettings(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings');
      onError?.(err instanceof Error ? err.message : 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      const updated = await oppfeedApi.updateSettings(settings);
      setSettings(updated);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings');
      onError?.(err instanceof Error ? err.message : 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
        Loading settings…
      </Card>
    );
  }

  if (!settings) {
    return (
      <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
        No settings available.
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
          Agent Settings
        </h2>
        <Button type="button" variant="primary" size="sm" disabled={saving} onClick={save}>
          Save
        </Button>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <Card className="p-3">
        <div className="space-y-3">
          <div>
            <p className="text-xs font-semibold mb-1" style={{ color: 'var(--cp-muted)' }}>
              Run Window (IST)
            </p>
            <div className="flex items-center gap-2">
              <Input
                value={settings.run_window_start}
                onChange={e => setSettings({ ...settings, run_window_start: e.target.value })}
                placeholder="02:00"
                className="w-24 text-xs"
              />
              <span className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                to
              </span>
              <Input
                value={settings.run_window_end}
                onChange={e => setSettings({ ...settings, run_window_end: e.target.value })}
                placeholder="04:00"
                className="w-24 text-xs"
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <label
              className="flex items-center gap-2 text-xs cursor-pointer"
              style={{ color: 'var(--cp-text)' }}
            >
              <input
                type="checkbox"
                checked={settings.auto_publish_enabled}
                onChange={e => setSettings({ ...settings, auto_publish_enabled: e.target.checked })}
                className="w-4 h-4 rounded"
              />
              Enable auto-publish
            </label>
          </div>

          <div>
            <p className="text-xs font-semibold mb-1" style={{ color: 'var(--cp-muted)' }}>
              Auto-Publish Threshold
            </p>
            <Input
              type="number"
              step="0.05"
              min="0"
              max="1"
              value={settings.auto_publish_threshold}
              onChange={e =>
                setSettings({
                  ...settings,
                  auto_publish_threshold: parseFloat(e.target.value) || 0,
                })
              }
              className="w-24 text-xs"
            />
          </div>

          <div className="flex items-center gap-2">
            <label
              className="flex items-center gap-2 text-xs cursor-pointer"
              style={{ color: 'var(--cp-text)' }}
            >
              <input
                type="checkbox"
                checked={settings.enable_agent}
                onChange={e => setSettings({ ...settings, enable_agent: e.target.checked })}
                className="w-4 h-4 rounded"
              />
              Enable Agent
            </label>
          </div>

          <div className="flex items-center gap-2">
            <label
              className="flex items-center gap-2 text-xs cursor-pointer"
              style={{ color: 'var(--cp-text)' }}
            >
              <input
                type="checkbox"
                checked={settings.enable_scheduler}
                onChange={e => setSettings({ ...settings, enable_scheduler: e.target.checked })}
                className="w-4 h-4 rounded"
              />
              Enable Scheduler
            </label>
          </div>

          <div>
            <p className="text-xs font-semibold mb-1" style={{ color: 'var(--cp-muted)' }}>
              LLM Provider Chain
            </p>
            <Input
              value={settings.llm_provider_chain}
              onChange={e => setSettings({ ...settings, llm_provider_chain: e.target.value })}
              placeholder="nvidia_nim,opencode_cli,openrouter,mock"
              className="text-xs font-mono"
            />
            <p className="text-[10px] mt-1" style={{ color: 'var(--cp-muted)' }}>
              Comma-separated provider names.
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold mb-1" style={{ color: 'var(--cp-muted)' }}>
              Max RPM
            </p>
            <Input
              type="number"
              value={settings.llm_max_rpm}
              onChange={e =>
                setSettings({ ...settings, llm_max_rpm: parseInt(e.target.value) || 30 })
              }
              className="w-24 text-xs"
            />
          </div>

          <div>
            <p className="text-xs font-semibold mb-1" style={{ color: 'var(--cp-muted)' }}>
              Max drafts per run
            </p>
            <Input
              type="number"
              min={0}
              max={500}
              value={settings.max_drafts_per_run ?? 100}
              onChange={e =>
                setSettings({
                  ...settings,
                  max_drafts_per_run: Math.max(0, parseInt(e.target.value) || 0),
                })
              }
              className="w-24 text-xs"
            />
            <p className="text-[10px] mt-1" style={{ color: 'var(--cp-muted)' }}>
              How many verified opportunities one run may write. The rest are reported, not quietly
              dropped.
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold mb-1" style={{ color: 'var(--cp-muted)' }}>
              Feature Flags
            </p>
            <div className="flex flex-wrap gap-2">
              <label
                className="flex items-center gap-1 text-xs cursor-pointer"
                style={{ color: 'var(--cp-text)' }}
              >
                <input
                  type="checkbox"
                  checked={settings.enable_vision}
                  onChange={e => setSettings({ ...settings, enable_vision: e.target.checked })}
                  className="w-4 h-4 rounded"
                />
                Vision
              </label>
              <label
                className="flex items-center gap-1 text-xs cursor-pointer"
                style={{ color: 'var(--cp-text)' }}
              >
                <input
                  type="checkbox"
                  checked={settings.enable_banner_gen}
                  onChange={e => setSettings({ ...settings, enable_banner_gen: e.target.checked })}
                  className="w-4 h-4 rounded"
                />
                Banner Gen
              </label>
              <label
                className="flex items-center gap-1 text-xs cursor-pointer"
                style={{ color: 'var(--cp-text)' }}
              >
                <input
                  type="checkbox"
                  checked={settings.enable_audio_summary}
                  onChange={e =>
                    setSettings({ ...settings, enable_audio_summary: e.target.checked })
                  }
                  className="w-4 h-4 rounded"
                />
                Audio Summary
              </label>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
