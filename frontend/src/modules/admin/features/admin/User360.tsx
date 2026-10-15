import { useState } from 'react';
import { User } from 'lucide-react';
import { adminApi } from '@/api';
import { Card, Badge, Input, Button, Tabs, Table } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';

export default function User360({ onError: _onError }: { onError?: (m: string) => void }) {
  const [user, setUser] = useState<{
    user: {
      id: number;
      email: string;
      username: string;
      full_name: string | null;
      roll_number: string | null;
      role: string;
      is_email_verified: boolean;
      created_at: string | null;
    };
    profile: {
      full_name: string | null;
      phone: string | null;
      branch: string | null;
      semester: number | null;
      programme: string | null;
    } | null;
    recent_events: Array<{ event_name: string; platform: string; created_at: string }>;
    teams: number[];
    recent_errors: Array<{ fingerprint: string; platform: string; created_at: string }>;
  } | null>(null);
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState<
    'profile' | 'devices' | 'sessions' | 'errors' | 'features' | 'teams' | 'moderation' | 'audit'
  >('profile');
  const handleTabChange = (id: string) =>
    setActiveTab(
      id as
        | 'profile'
        | 'devices'
        | 'sessions'
        | 'errors'
        | 'features'
        | 'teams'
        | 'moderation'
        | 'audit'
    );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadUser = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await adminApi.user360(id);
      setUser(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'User not found');
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && search.trim()) {
      loadUser(search.trim());
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <div className="flex-1 max-w-md">
          <Input
            id="user360-search"
            value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={handleSearch}
            placeholder="Search by user ID, email, username, or roll number…"
            className="w-full"
          />
        </div>
        <Button
          variant="primary"
          size="sm"
          onClick={() => search.trim() && loadUser(search.trim())}
          disabled={loading || !search.trim()}
        >
          Search
        </Button>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {user && (
        <>
          <Card>
            <div className="flex items-center gap-4 p-4">
              <div className="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center">
                <User size={32} className="text-blue-600" />
              </div>
              <div>
                <h2 className="text-xl font-semibold">{user.user.username}</h2>
                <p className="text-sm text-gray-500">
                  {user.user.email} · {user.user.roll_number || 'No roll number'}
                </p>
                <div className="flex items-center gap-3 mt-1">
                  <Badge tone={user.user.role === 'admin' ? 'primary' : 'neutral'}>
                    {user.user.role}
                  </Badge>
                  <Badge tone={user.user.is_email_verified ? 'success' : 'warning'}>
                    {user.user.is_email_verified ? 'Verified' : 'Unverified'}
                  </Badge>
                </div>
              </div>
            </div>
          </Card>

          <Tabs
            tabs={[
              { id: 'profile', label: 'Profile' },
              { id: 'devices', label: 'Devices' },
              { id: 'sessions', label: 'Sessions' },
              { id: 'errors', label: 'Errors' },
              { id: 'features', label: 'Features' },
              { id: 'teams', label: 'Teams' },
              { id: 'moderation', label: 'Moderation' },
              { id: 'audit', label: 'Audit' },
            ]}
            active={activeTab}
            onChange={handleTabChange}
          />

          <ErrorBanner message={error} onDismiss={() => setError(null)} />

          {activeTab === 'profile' && (
            <Card className="mt-4 space-y-2">
              <h3 className="text-lg font-semibold">Profile</h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">Full Name</span>
                  <p>{user.profile?.full_name || '—'}</p>
                </div>
                <div>
                  <span className="text-gray-500">Branch</span>
                  <p>{user.profile?.branch || '—'}</p>
                </div>
                <div>
                  <span className="text-gray-500">Semester</span>
                  <p>{user.profile?.semester || '—'}</p>
                </div>
                <div>
                  <span className="text-gray-500">Programme</span>
                  <p>{user.profile?.programme || '—'}</p>
                </div>
                <div>
                  <span className="text-gray-500">Phone</span>
                  <p>{user.profile?.phone || '—'}</p>
                </div>
                <div>
                  <span className="text-gray-500">Created</span>
                  <p>
                    {user.user.created_at ? new Date(user.user.created_at).toLocaleString() : '—'}
                  </p>
                </div>
              </div>
            </Card>
          )}

          {activeTab === 'devices' && (
            <Card className="mt-4">
              <h3 className="text-lg font-semibold mb-2">Devices</h3>
              <p className="text-gray-500">Device tracking not yet implemented.</p>
            </Card>
          )}

          {activeTab === 'sessions' && (
            <Card className="mt-4">
              <h3 className="text-lg font-semibold mb-2">Sessions</h3>
              <p className="text-gray-500">Session history not yet implemented.</p>
            </Card>
          )}

          {activeTab === 'errors' && (
            <Card className="mt-4">
              <h3 className="text-lg font-semibold mb-2">Recent Errors</h3>
              {user.recent_errors?.length ? (
                <Table
                  head={['Fingerprint', 'Platform', 'Time']}
                  rows={user.recent_errors.map(
                    (e: { fingerprint: string; platform: string; created_at: string }) => [
                      <code key="f" className="text-xs">
                        {e.fingerprint}
                      </code>,
                      <Badge key="p" tone="neutral">
                        {e.platform}
                      </Badge>,
                      <span key="t">
                        {e.created_at ? new Date(e.created_at).toLocaleString() : '—'}
                      </span>,
                    ]
                  )}
                />
              ) : (
                <p className="text-gray-500">No recent errors.</p>
              )}
            </Card>
          )}

          {activeTab === 'features' && (
            <Card className="mt-4">
              <h3 className="text-lg font-semibold mb-2">Feature Usage</h3>
              <p className="text-gray-500">Feature usage per user not yet implemented.</p>
            </Card>
          )}

          {activeTab === 'teams' && (
            <Card className="mt-4">
              <h3 className="text-lg font-semibold mb-2">Team Memberships</h3>
              <p className="text-gray-500">Team data not yet implemented.</p>
            </Card>
          )}

          {activeTab === 'moderation' && (
            <Card className="mt-4">
              <h3 className="text-lg font-semibold mb-2">Moderation History</h3>
              <p className="text-gray-500">Moderation history not yet implemented.</p>
            </Card>
          )}

          {activeTab === 'audit' && (
            <Card className="mt-4">
              <h3 className="text-lg font-semibold mb-2">Audit Trail</h3>
              <p className="text-gray-500">User-specific audit log not yet implemented.</p>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
