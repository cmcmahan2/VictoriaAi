'use client';
import { useCallback, useEffect, useState } from 'react';
import { useStore } from '@/lib/store';
import { streak } from '@/lib/calc';
import Dashboard from './screens/Dashboard';
import CheckIn from './screens/CheckIn';
import Spending from './screens/Spending';
import DebtScreen from './screens/Debt';
import Savings from './screens/Savings';
import Vehicle from './screens/Vehicle';
import ImportScreen from './screens/Import';
import Settings from './screens/Settings';
import { Sheet } from './ui';

export type Tab = 'home' | 'checkin' | 'spending' | 'debt' | 'savings' | 'vehicle' | 'import' | 'settings';
const TABS: Tab[] = ['home', 'checkin', 'spending', 'debt', 'savings', 'vehicle', 'import', 'settings'];
const MORE: Tab[] = ['vehicle', 'import', 'settings'];

const ICONS: Record<string, JSX.Element> = {
  home: <path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z" />,
  spending: <><path d="M4 6h16M4 12h16M4 18h10" /></>,
  debt: <><path d="M3 7l6 6 4-4 8 8" /><path d="M21 11v6h-6" /></>,
  more: <><circle cx="5" cy="12" r="1.6" /><circle cx="12" cy="12" r="1.6" /><circle cx="19" cy="12" r="1.6" /></>,
};
const Icon = ({ name }: { name: string }) => (
  <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>{ICONS[name]}</svg>
);

const readHash = (): Tab => {
  const h = (typeof window !== 'undefined' ? window.location.hash.slice(1) : '') as Tab;
  return TABS.includes(h) ? h : 'home';
};

export default function Shell() {
  const { state, saveError } = useStore();
  const [tab, setTab] = useState<Tab>('home');
  const [more, setMore] = useState(false);

  useEffect(() => {
    setTab(readHash());
    const on = () => setTab(readHash());
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);

  const go = useCallback((t: Tab) => {
    setMore(false);
    if (window.location.hash.slice(1) !== t) window.location.hash = t;
    setTab(t);
    window.scrollTo({ top: 0 });
  }, []);

  const st = streak(state);
  const item = (t: Tab, icon: string, label: string) => (
    <button className={`tab ${tab === t ? 'on' : ''}`} onClick={() => go(t)} aria-current={tab === t ? 'page' : undefined}>
      <span className="tab-i"><Icon name={icon} /></span>
      <span className="tab-l">{label}</span>
    </button>
  );

  return (
    <div className="app">
      {saveError && <div className="banner red">{saveError}</div>}
      <main key={tab}>
        {tab === 'home' && <Dashboard go={go} />}
        {tab === 'checkin' && <CheckIn go={go} />}
        {tab === 'spending' && <Spending />}
        {tab === 'debt' && <DebtScreen />}
        {tab === 'savings' && <Savings />}
        {tab === 'vehicle' && <Vehicle />}
        {tab === 'import' && <ImportScreen />}
        {tab === 'settings' && <Settings />}
      </main>
      <nav className="tabbar" aria-label="Main">
        {item('home', 'home', 'Home')}
        {item('spending', 'spending', 'Spending')}
        <button className={`plus ${tab === 'checkin' ? 'on' : ''} ${!st.today ? 'pulse' : ''}`} onClick={() => go('checkin')} aria-label="Today's spending check-in">＋</button>
        {item('debt', 'debt', 'Debt')}
        <button className={`tab ${MORE.includes(tab) || tab === 'savings' ? 'on' : ''}`} onClick={() => setMore(true)} aria-haspopup="dialog">
          <span className="tab-i"><Icon name="more" /></span>
          <span className="tab-l">More</span>
        </button>
      </nav>
      <Sheet open={more} onClose={() => setMore(false)} title="More">
        <div className="menu">
          <button onClick={() => go('savings')}><span>🛟</span>Savings & investing</button>
          <button onClick={() => go('vehicle')}><span>🚗</span>Work vehicle tracker</button>
          <button onClick={() => go('import')}><span>🏦</span>Import bank statements</button>
          <button onClick={() => go('settings')}><span>⚙️</span>Settings & backup</button>
        </div>
      </Sheet>
    </div>
  );
}
