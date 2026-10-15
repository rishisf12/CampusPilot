import { useEffect, useState, ChangeEvent } from 'react';
import { FlaskConical, Plus, Trash2 } from 'lucide-react';
import { reinforcementApi, type ReinforcementPattern } from '@/api';
import { Badge, Button, Card, Input, Toggle } from '@/components/ui';

interface ReinforcementPatternsProps {
  onError?: (message: string) => void;
}

export default function ReinforcementPatterns({ onError }: ReinforcementPatternsProps) {
  const [patterns, setPatterns] = useState<ReinforcementPattern[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testInput, setTestInput] = useState('');
  const [testOutput, setTestOutput] = useState('');
  const [testMatched, setTestMatched] = useState<boolean | null>(null);
  const [testing, setTesting] = useState(false);
  const [newPattern, setNewPattern] = useState({
    name: '',
    pattern: '',
    replacement: '',
    description: '',
  });
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setPatterns(await reinforcementApi.list());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load patterns');
      onError?.(err instanceof Error ? err.message : 'Failed to load patterns');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const testPattern = async () => {
    setTesting(true);
    try {
      const result = await reinforcementApi.test({
        pattern: newPattern.pattern,
        replacement: newPattern.replacement,
        text: testInput,
      });
      setTestOutput(result.output);
      setTestMatched(result.matched);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Test failed');
    } finally {
      setTesting(false);
    }
  };

  const addPattern = async () => {
    setSaving(true);
    try {
      await reinforcementApi.create(newPattern);
      setNewPattern({ name: '', pattern: '', replacement: '', description: '' });
      setTestOutput('');
      setTestMatched(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add pattern');
    } finally {
      setSaving(false);
    }
  };

  const togglePattern = async (id: number, enabled: boolean) => {
    try {
      await reinforcementApi.update(id, { enabled });
      setPatterns(prev => prev.map(p => (p.id === id ? { ...p, enabled } : p)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update pattern');
    }
  };

  const deletePattern = async (id: number) => {
    if (!window.confirm('Delete this pattern?')) return;
    try {
      await reinforcementApi.remove(id);
      setPatterns(prev => prev.filter(p => p.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete pattern');
    }
  };

  if (loading) {
    return (
      <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
        Loading patterns…
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
          Reinforcement Patterns
        </h2>
        <p className="text-sm mt-1" style={{ color: 'var(--cp-muted)' }}>
          Patterns learned from PDF parsing mistakes. Applied automatically during timetable
          parsing.
        </p>
      </Card>

      {error && (
        <div
          className="p-3 text-sm"
          style={{
            borderRadius: 12,
            border: '1px solid rgba(163,177,198,.3)',
            background: 'var(--cp-bg)',
            boxShadow: 'var(--cp-neu-inset)',
            color: 'var(--cp-danger)',
          }}
          aria-live="polite"
        >
          {error}
        </div>
      )}

      <Card className="space-y-4">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
          Add New Pattern
        </h3>
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <span className="label">Pattern name</span>
            <Input
              id="rp-name"
              type="text"
              placeholder="Pattern name"
              value={newPattern.name}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setNewPattern(p => ({ ...p, name: e.target.value }))
              }
            />
          </div>
          <div>
            <span className="label">Regex pattern</span>
            <Input
              id="rp-pattern"
              type="text"
              placeholder="Regex pattern"
              value={newPattern.pattern}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setNewPattern(p => ({ ...p, pattern: e.target.value }))
              }
              className="font-mono"
            />
          </div>
          <div>
            <span className="label">Replacement</span>
            <Input
              id="rp-replacement"
              type="text"
              placeholder="Replacement"
              value={newPattern.replacement}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setNewPattern(p => ({ ...p, replacement: e.target.value }))
              }
            />
          </div>
          <div>
            <span className="label">Description</span>
            <Input
              id="rp-description"
              type="text"
              placeholder="Description (what this fixes)"
              value={newPattern.description}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setNewPattern(p => ({ ...p, description: e.target.value }))
              }
            />
          </div>
          <div>
            <span className="label">Test input</span>
            <Input
              id="rp-test-input"
              type="text"
              placeholder="Test input"
              value={testInput}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setTestInput(e.target.value)}
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="primary"
            size="sm"
            icon={<Plus size={16} strokeWidth={2} aria-hidden />}
            loading={saving}
            disabled={saving || !newPattern.name || !newPattern.pattern || !newPattern.replacement}
            onClick={addPattern}
          >
            Add Pattern
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            icon={<FlaskConical size={16} strokeWidth={2} aria-hidden />}
            loading={testing}
            disabled={testing || !newPattern.pattern || !newPattern.replacement || !testInput}
            title="Preview this pattern against the test input without saving it"
            onClick={testPattern}
          >
            Test
          </Button>
        </div>
        {testOutput !== '' && (
          <div
            className="p-3 text-sm"
            style={{
              borderRadius: 12,
              background: 'var(--cp-bg)',
              boxShadow: 'var(--cp-neu-inset)',
            }}
            aria-live="polite"
          >
            <p className="font-mono" style={{ color: 'var(--cp-muted)' }}>
              Input: {testInput}
            </p>
            <p
              className="font-mono mt-1"
              style={{ color: testMatched ? 'var(--cp-success)' : 'var(--cp-warning)' }}
            >
              Output: {testOutput}
            </p>
            <p className="text-xs mt-1" style={{ color: 'var(--cp-muted)' }}>
              {testMatched
                ? 'Pattern matched and rewrote the input.'
                : 'No match — the output is identical to the input.'}
            </p>
          </div>
        )}
      </Card>

      <Card>
        <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
          Active Patterns ({patterns.length})
        </h3>
        <div className="space-y-2 mt-3" aria-live="polite">
          {patterns.map(p => (
            <div
              key={p.id}
              className="flex items-start gap-3 p-3"
              style={{
                borderRadius: 12,
                border: '1px solid rgba(163,177,198,.3)',
                background: 'var(--cp-bg)',
                boxShadow: 'var(--cp-neu-inset)',
              }}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm" style={{ color: 'var(--cp-text)' }}>
                    {p.name}
                  </span>
                  <Badge tone={p.enabled ? 'success' : 'neutral'}>
                    {p.enabled ? 'Enabled' : 'Disabled'}
                  </Badge>
                </div>
                <p className="text-xs mt-1" style={{ color: 'var(--cp-muted)' }}>
                  {p.description}
                </p>
                <p
                  className="font-mono text-xs mt-1 break-all"
                  style={{ color: 'var(--cp-muted)' }}
                >
                  {p.pattern}
                </p>
                <p className="font-mono text-xs" style={{ color: 'var(--cp-muted)' }}>
                  → {p.replacement}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Toggle
                  checked={p.enabled}
                  onClick={() => togglePattern(p.id, !p.enabled)}
                  aria-label={`${p.enabled ? 'Disable' : 'Enable'} pattern ${p.name}`}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  icon={<Trash2 size={16} strokeWidth={2} aria-hidden />}
                  aria-label={`Delete pattern ${p.name}`}
                  onClick={() => deletePattern(p.id)}
                />
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
