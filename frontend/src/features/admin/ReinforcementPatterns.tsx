import { useEffect, useState, ChangeEvent } from 'react';
import { reinforcementApi, type ReinforcementPattern } from '../../api';

interface ReinforcementPatternsProps {
  onError?: (message: string) => void;
}

export default function ReinforcementPatterns({ onError }: ReinforcementPatternsProps) {
  const [patterns, setPatterns] = useState<ReinforcementPattern[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testInput, setTestInput] = useState('');
  const [testOutput, setTestOutput] = useState('');
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
    try {
      const result = await reinforcementApi.test({
        pattern: newPattern.pattern,
        description: testInput,
      });
      setTestOutput(result.output);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Test failed');
    }
  };

  const addPattern = async () => {
    setSaving(true);
    try {
      await reinforcementApi.create(newPattern);
      setNewPattern({ name: '', pattern: '', replacement: '', description: '' });
      setTestOutput('');
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
    return <div className="card p-8 text-center text-sm text-gray-500">Loading patterns…</div>;
  }

  return (
    <div className="space-y-4">
      <div className="card p-6">
        <h2 className="text-lg font-semibold text-gray-900">Reinforcement Patterns</h2>
        <p className="text-sm text-gray-600 mt-1">
          Patterns learned from PDF parsing mistakes. Applied automatically during timetable
          parsing.
        </p>
      </div>

      {error && (
        <div className="p-3 rounded-lg border border-red-200 bg-red-50 text-red-700 text-sm">
          {error}
        </div>
      )}

      <div className="card p-6 space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Add New Pattern</h3>
        <div className="grid md:grid-cols-2 gap-4">
          <input
            type="text"
            placeholder="Pattern name"
            value={newPattern.name}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              setNewPattern(p => ({ ...p, name: e.target.value }))
            }
            className="rounded-lg border border-gray-200 px-3 py-2 text-sm"
          />
          <input
            type="text"
            placeholder="Regex pattern"
            value={newPattern.pattern}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              setNewPattern(p => ({ ...p, pattern: e.target.value }))
            }
            className="rounded-lg border border-gray-200 px-3 py-2 text-sm font-mono"
          />
          <input
            type="text"
            placeholder="Replacement"
            value={newPattern.replacement}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              setNewPattern(p => ({ ...p, replacement: e.target.value }))
            }
            className="rounded-lg border border-gray-200 px-3 py-2 text-sm"
          />
          <input
            type="text"
            placeholder="Test input"
            value={testInput}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setTestInput(e.target.value)}
            className="rounded-lg border border-gray-200 px-3 py-2 text-sm"
          />
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={addPattern}
            disabled={saving || !newPattern.name || !newPattern.pattern || !newPattern.replacement}
            className="btn-primary text-sm disabled:opacity-60"
          >
            {saving ? 'Adding…' : 'Add Pattern'}
          </button>
          <button
            type="button"
            onClick={testPattern}
            disabled={!newPattern.pattern || !testInput}
            className="btn-ghost text-sm disabled:opacity-60"
          >
            Test
          </button>
        </div>
        {testOutput && (
          <div className="p-3 rounded-lg bg-gray-50 text-sm">
            <p className="font-mono text-gray-600">Input: {testInput}</p>
            <p className="font-mono text-green-600 mt-1">Output: {testOutput}</p>
          </div>
        )}
      </div>

      <div className="card p-6">
        <h3 className="text-sm font-semibold text-gray-900">Active Patterns ({patterns.length})</h3>
        <div className="space-y-2 mt-3">
          {patterns.map(p => (
            <div
              key={p.id}
              className="flex items-start gap-3 p-3 rounded-lg border border-gray-100 bg-gray-50/60"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm text-gray-900">{p.name}</span>
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      p.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                    }`}
                  >
                    {p.enabled ? 'Enabled' : 'Disabled'}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-1">{p.description}</p>
                <p className="font-mono text-xs text-gray-600 mt-1 break-all">{p.pattern}</p>
                <p className="font-mono text-xs text-gray-600">→ {p.replacement}</p>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button
                  type="button"
                  onClick={() => togglePattern(p.id, !p.enabled)}
                  className="px-2 py-1 text-xs rounded border border-gray-200 hover:bg-gray-50"
                >
                  {p.enabled ? 'Disable' : 'Enable'}
                </button>
                <button
                  type="button"
                  onClick={() => deletePattern(p.id)}
                  className="px-2 py-1 text-xs rounded border border-gray-200 hover:bg-red-50 text-red-600"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
