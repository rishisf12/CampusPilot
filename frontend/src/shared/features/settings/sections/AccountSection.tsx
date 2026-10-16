import { ExternalLink, RotateCcw, Trash2 } from 'lucide-react';
import { Button, Card } from '@/components/ui';
import ManagePasskeys from '@shared/auth/ManagePasskeys';
import { readQuickLookup, writeQuickLookup } from '@shared/lib/storage';
import { useState } from 'react';
import { resetAllSettings } from '../useSettings';

/**
 * Account pane.
 *
 * Holds the account-level controls, and *links* to Profile rather than
 * reimplementing it. Programme, semester, branch and electives are the profile's
 * single source of truth, written through the profile API; a second editor here
 * would be a second copy that eventually disagrees with the first.
 *
 * The Profile button needs the module's section setter, which shared/ cannot
 * reach, so the module passes `onOpenProfile` in. Without it the row explains
 * where Profile lives instead of offering a dead control.
 */

export interface AccountPaneProps {
  /** Opens the module's Profile page. Absent means this pane cannot navigate. */
  onOpenProfile?: () => void;
}

export default function AccountSection({ onOpenProfile }: AccountPaneProps) {
  const [cleared, setCleared] = useState(false);
  const [reset, setReset] = useState(false);

  const clearCachedLookups = () => {
    writeQuickLookup(null);
    setCleared(true);
  };

  return (
    <div className="space-y-4">
      <Card className="space-y-3">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
          Profile
        </h3>
        <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
          Your programme, semester, branch and electives decide which timetable, rooms and exams the
          app shows you.
        </p>
        {onOpenProfile ? (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            icon={<ExternalLink size={16} strokeWidth={2} aria-hidden />}
            onClick={onOpenProfile}
          >
            Open Profile
          </Button>
        ) : (
          <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
            Open Profile from the sidebar menu.
          </p>
        )}
      </Card>

      <Card className="space-y-3">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
          Sign-in
        </h3>
        <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
          Passkeys let you sign in with your fingerprint, face or device PIN. Revoke one that is on
          a device you no longer have.
        </p>
        <ManagePasskeys />
      </Card>

      <Card className="space-y-3">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
          Cached data
        </h3>
        <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
          The last exam seat lookup is kept on this device so a refresh does not ask for your roll
          number again. Clearing it signs nothing out.
        </p>
        <div className="flex items-center gap-3">
          <Button
            type="button"
            variant="danger"
            size="sm"
            icon={<Trash2 size={16} strokeWidth={2} aria-hidden />}
            onClick={clearCachedLookups}
          >
            Clear cached lookups
          </Button>
          {cleared && (
            <span className="text-xs" style={{ color: 'var(--cp-success)' }}>
              Cleared.
            </span>
          )}
        </div>
        {readQuickLookup() && !cleared && (
          <p className="text-[11px]" style={{ color: 'var(--cp-muted)' }}>
            A cached lookup is stored on this device.
          </p>
        )}
      </Card>

      <Card className="space-y-3">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
          Reset settings
        </h3>
        <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
          Puts every setting on this account back to its default, including the ones saved on your
          other devices. Your profile, timetable and passkeys are not affected.
        </p>
        <div className="flex items-center gap-3">
          <Button
            type="button"
            variant="danger"
            size="sm"
            icon={<RotateCcw size={16} strokeWidth={2} aria-hidden />}
            onClick={() => {
              // Destructive and hard to undo from the settings page itself, so it
              // asks first - unlike the per-section resets, which are one tab away.
              if (!window.confirm('Reset every setting on your account?')) return;
              resetAllSettings();
              setReset(true);
            }}
          >
            Reset all settings
          </Button>
          {reset && (
            <span className="text-xs" style={{ color: 'var(--cp-success)' }}>
              Everything is back to default.
            </span>
          )}
        </div>
      </Card>
    </div>
  );
}
