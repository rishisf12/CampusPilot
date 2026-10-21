/**
 * OppFeed: the agent that finds opportunities, and the screens that work on
 * it.
 *
 * These are one feature, not five sections: the dashboard is the agent's
 * overview, the runs are its history, the opportunities are what it found,
 * the settings are its configuration, and the LLM status is the providers it
 * talks to. So they live under one entry in the admin's navigation with a
 * sub-nav of their own - the way the admin panel keeps its own sections
 * under one entry - instead of five entries pretending to be five features.
 */
import { Suspense, lazy, useState } from 'react';
import { Activity, Bot, Briefcase, Settings2, TrendingUp } from 'lucide-react';
import { Tabs } from '@/components/ui';
import Spinner from '@shared/components/Spinner';

const OppFeedDashboard = lazy(() => import('./OppFeedDashboard'));
const AgentRunsList = lazy(() => import('./AgentRunsList'));
const OpportunitiesManager = lazy(() => import('./OpportunitiesManager'));
const AgentSettings = lazy(() => import('./AgentSettings'));
const LLMStatus = lazy(() => import('./LLMStatus'));

const SUB_TABS = [
  { id: 'dashboard', label: 'Dashboard', icon: <TrendingUp size={16} strokeWidth={2} /> },
  { id: 'runs', label: 'Agent Runs', icon: <Activity size={16} strokeWidth={2} /> },
  {
    id: 'opportunities',
    label: 'Opportunities',
    icon: <Briefcase size={16} strokeWidth={2} />,
  },
  { id: 'settings', label: 'Agent Settings', icon: <Settings2 size={16} strokeWidth={2} /> },
  { id: 'llm', label: 'LLM Status', icon: <Bot size={16} strokeWidth={2} /> },
] as const;

type SubTab = (typeof SUB_TABS)[number]['id'];

function SectionLoading() {
  return (
    <div className="flex justify-center py-12">
      <Spinner size={24} />
    </div>
  );
}

export default function OppFeed({ onError }: { onError?: (m: string) => void }) {
  const [tab, setTab] = useState<SubTab>('dashboard');

  return (
    <div className="space-y-4">
      <Tabs
        tabs={SUB_TABS.map(item => ({ id: item.id, label: item.label, icon: item.icon }))}
        active={tab}
        onChange={id => setTab(id as SubTab)}
      />

      <Suspense fallback={<SectionLoading />}>
        {tab === 'dashboard' && <OppFeedDashboard onError={onError} />}
        {tab === 'runs' && <AgentRunsList onError={onError} />}
        {tab === 'opportunities' && <OpportunitiesManager onError={onError} />}
        {tab === 'settings' && <AgentSettings onError={onError} />}
        {tab === 'llm' && <LLMStatus onError={onError} />}
      </Suspense>
    </div>
  );
}
