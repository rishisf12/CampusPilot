import type { SettingsSectionId } from '@shared/constants';
import AccountSection, { type AccountPaneProps } from '../sections/AccountSection';

/** Which pane backs each Settings tab. */
export type Pane =
  { kind: 'registry' } | { kind: 'custom'; render: (props: AccountPaneProps) => React.ReactNode };

export const PANES: Record<SettingsSectionId, Pane> = {
  appearance: { kind: 'registry' },
  notifications: { kind: 'registry' },
  schedule: { kind: 'registry' },
  account: { kind: 'custom', render: props => <AccountSection {...props} /> },
};
