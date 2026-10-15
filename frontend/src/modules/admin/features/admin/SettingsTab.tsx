import { useEffect, useState, type ChangeEvent, type ChangeEventHandler } from 'react';
import { Shield, Database, Zap, Wrench, Bell, Globe } from 'lucide-react';
import { adminApi } from '@/api';
import { Card } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';

type SettingValue = string | number | boolean;
interface Settings {
  rate_limiting_enabled?: boolean;
  brute_force_protection?: boolean;
  password_min_length?: number;
  auto_vacuum?: boolean;
  query_timeout?: number;
  default_rollout_percentage?: number;
  default_maintenance_message?: string;
  alert_email?: string;
  slack_webhook_url?: string;
  ios_app_store_url?: string;
  android_play_store_url?: string;
}

export default function SettingsTab({ onError }: { onError?: (m: string) => void }) {
  const [settings, setSettings] = useState<Settings>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await adminApi.getSettings();
      setSettings(data as Settings);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
      onError?.(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  const save = async (key: string, value: SettingValue) => {
    setSaving(true);
    try {
      await adminApi.updateSetting(key, value);
      setSettings((prev: Settings) => ({ ...prev, [key]: value }));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading)
    return (
      <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
        Loading settings…
      </Card>
    );

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">System Settings</h2>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <Card>
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Shield size={20} /> Security
        </h3>
        <div className="space-y-4">
          <SettingRow
            label="Rate Limiting"
            description="Enable API rate limiting"
            type="checkbox"
            checked={settings.rate_limiting_enabled ?? true}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              save('rate_limiting_enabled', e.target.checked)
            }
            disabled={saving}
          />
          <SettingRow
            label="Brute Force Protection"
            description="Lock accounts after failed attempts"
            type="checkbox"
            checked={settings.brute_force_protection ?? true}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              save('brute_force_protection', e.target.checked)
            }
            disabled={saving}
          />
          <SettingRow
            label="Password Min Length"
            description="Minimum password length"
            type="number"
            value={settings.password_min_length ?? 8}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              save('password_min_length', parseInt(e.target.value))
            }
            min={6}
            max={64}
            disabled={saving}
          />
        </div>
      </Card>

      <Card>
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Database size={20} /> Database
        </h3>
        <div className="space-y-4">
          <SettingRow
            label="Auto Vacuum"
            description="Automatic vacuum on schedule"
            type="checkbox"
            checked={settings.auto_vacuum ?? true}
            onChange={(e: ChangeEvent<HTMLInputElement>) => save('auto_vacuum', e.target.checked)}
            disabled={saving}
          />
          <SettingRow
            label="Query Timeout (seconds)"
            description="Max query execution time"
            type="number"
            value={settings.query_timeout ?? 30}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              save('query_timeout', parseInt(e.target.value))
            }
            min={5}
            max={300}
            disabled={saving}
          />
        </div>
      </Card>

      <Card>
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Zap size={20} /> Feature Flags
        </h3>
        <div className="space-y-4">
          <SettingRow
            label="Default Rollout %"
            description="Default rollout percentage for new flags"
            type="number"
            value={settings.default_rollout_percentage ?? 0}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              save('default_rollout_percentage', parseInt(e.target.value))
            }
            min={0}
            max={100}
            disabled={saving}
          />
        </div>
      </Card>

      <Card>
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Wrench size={20} /> Maintenance
        </h3>
        <div className="space-y-4">
          <SettingRow
            label="Default Maintenance Message"
            description="Shown during maintenance windows"
            type="textarea"
            value={
              settings.default_maintenance_message ||
              'Service temporarily unavailable. Please try again later.'
            }
            // The handler only reads e.target.value, which exists on both input
            // and textarea events, so the input event type is sufficient here.
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              save('default_maintenance_message', e.target.value)
            }
            rows={3}
            disabled={saving}
          />
        </div>
      </Card>

      <Card>
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Bell size={20} /> Notifications
        </h3>
        <div className="space-y-4">
          <SettingRow
            label="Alert Email"
            description="Email for system alerts"
            type="email"
            value={settings.alert_email || ''}
            onChange={(e: ChangeEvent<HTMLInputElement>) => save('alert_email', e.target.value)}
            placeholder="admin@example.com"
            disabled={saving}
          />
          <SettingRow
            label="Slack Webhook URL"
            description="For alert notifications"
            type="url"
            value={settings.slack_webhook_url || ''}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              save('slack_webhook_url', e.target.value)
            }
            placeholder="https://hooks.slack.com/services/..."
            disabled={saving}
          />
        </div>
      </Card>

      <Card>
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Globe size={20} /> Platform
        </h3>
        <div className="space-y-4">
          <SettingRow
            label="App Store URL (iOS)"
            description="For force update redirects"
            type="url"
            value={settings.ios_app_store_url || ''}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              save('ios_app_store_url', e.target.value)
            }
            placeholder="https://apps.apple.com/app/id..."
            disabled={saving}
          />
          <SettingRow
            label="Play Store URL (Android)"
            description="For force update redirects"
            type="url"
            value={settings.android_play_store_url || ''}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              save('android_play_store_url', e.target.value)
            }
            placeholder="https://play.google.com/store/apps/details?id=..."
            disabled={saving}
          />
        </div>
      </Card>
    </div>
  );
}

interface SettingRowProps {
  label: string;
  description: string;
  type: 'checkbox' | 'number' | 'email' | 'url' | 'textarea';
  checked?: boolean;
  value?: string | number;
  // Method syntax (not a property arrow) so parameter checking is bivariant:
  // eleven rows pass input handlers and one passes a textarea handler. A
  // property-style union parameter would be contravariant and reject both,
  // which is the error this replaces. The single cast at the raw <textarea>
  // below is the price; it is commented there.
  onChange(e: ChangeEvent<HTMLInputElement>): void;
  min?: number;
  max?: number;
  placeholder?: string;
  rows?: number;
  disabled?: boolean;
}

function SettingRow({
  label,
  description,
  type,
  checked,
  value,
  onChange,
  min,
  max,
  placeholder,
  rows,
  disabled,
}: SettingRowProps) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <p className="font-medium">{label}</p>
        <p className="text-sm text-gray-500">{description}</p>
      </div>
      {type === 'checkbox' && (
        <input
          type="checkbox"
          checked={checked}
          onChange={onChange}
          disabled={disabled}
          className="w-5 h-5 text-blue-600 rounded border-gray-300"
        />
      )}
      {type === 'number' && (
        <input
          type="number"
          value={value}
          onChange={onChange}
          min={min}
          max={max}
          disabled={disabled}
          className="w-24 rounded-lg border border-gray-200 px-3 py-1.5 text-sm"
        />
      )}
      {type === 'email' && (
        <input
          type="email"
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          disabled={disabled}
          className="w-64 rounded-lg border border-gray-200 px-3 py-1.5 text-sm"
        />
      )}
      {type === 'url' && (
        <input
          type="url"
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          disabled={disabled}
          className="w-96 rounded-lg border border-gray-200 px-3 py-1.5 text-sm"
        />
      )}
      {type === 'textarea' && (
        <textarea
          value={value}
          // One contained cast: the shared handler is typed for inputs (eleven
          // rows) and this is the single textarea. e.target.value exists on
          // both elements, so nothing is lost.
          onChange={onChange as unknown as ChangeEventHandler<HTMLTextAreaElement>}
          rows={rows}
          disabled={disabled}
          className="w-full rounded-lg border border-gray-200 px-3 py-1.5 text-sm"
        />
      )}
    </div>
  );
}
