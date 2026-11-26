import type { AppState, Category, Debt, Rule } from './types';

export const STORAGE_KEY = 'pocketplan:v1';
export const SCHEMA_VERSION = 1;

export const DEFAULT_CATEGORIES: Category[] = [
  {
    id: 'eating', name: 'Eating out', emoji: '🍔', color: '#ff8a5b', amount: 100, period: 'week', fixed: false,
    keywords: ['lunch', 'dinner', 'breakfast', 'food', 'coffee', 'starbucks', 'tims', 'mcdonalds', 'sushi', 'pizza', 'burger', 'uber eats', 'doordash', 'skip', 'restaurant', 'cafe', 'snack', 'takeout'],
  },
  {
    id: 'drinks', name: 'Drinks & going out', emoji: '🍻', color: '#b583ff', amount: 60, period: 'week', fixed: false,
    keywords: ['drinks', 'beer', 'bar', 'pub', 'club', 'bowling', 'movie', 'concert', 'tickets', 'liquor', 'bcl', 'shots', 'cover', 'party', 'game'],
  },
  {
    id: 'gas', name: 'Gas', emoji: '⛽', color: '#4cc9f0', amount: 75, period: 'week', fixed: false,
    keywords: ['gas', 'fuel', 'esso', 'shell', 'petro', 'chevron', 'husky', 'fill'],
  },
  {
    id: 'lifestyle', name: 'Lifestyle', emoji: '🛍️', color: '#f472b6', amount: 400, period: 'month', fixed: false,
    keywords: ['clothes', 'shoes', 'golf', 'balls', 'clubs', 'zyn', 'zyns', 'vape', 'shirt', 'hoodie', 'pants', 'amazon', 'haircut', 'nike', 'lulu'],
  },
  {
    id: 'insurance', name: 'Car insurance', emoji: '🚗', color: '#94a3b8', amount: 175, period: 'month', fixed: true,
    keywords: ['icbc', 'insurance'],
  },
  {
    id: 'other', name: 'Other', emoji: '📦', color: '#a3a3a3', amount: 0, period: 'month', fixed: false,
    keywords: [],
  },
  {
    id: 'ignore', name: 'Transfer / ignore', emoji: '↔️', color: '#4b5563', amount: 0, period: 'month', fixed: false, ignore: true,
    keywords: [],
  },
];

const now = () => Date.now();

export const DEFAULT_DEBTS = (): Debt[] => [
  { id: 'amex', name: 'Amex Cobalt', kind: 'card', apr: 21.99, color: '#60a5fa', originalBalance: 850, balance: 850, balanceSetAt: now(), note: 'Pay in full every month once cleared.' },
  { id: 'tangerine', name: 'Tangerine (gas card)', kind: 'card', apr: 20.95, color: '#fb923c', originalBalance: 1000, balance: 1000, balanceSetAt: now(), note: 'Gas only.' },
  { id: 'student', name: 'Student loan', kind: 'loan', apr: 0, color: '#fbbf24', originalBalance: 9500, balance: 9500, balanceSetAt: now(), deadline: '2028-11-30', note: 'Must be paid off within 2 years. BC & federal student loans are currently interest-free — edit the APR if yours isn’t.' },
];

const r = (match: string, categoryId: string, i: number): Rule => ({ id: `r${i}`, match, categoryId });

export const DEFAULT_RULES = (): Rule[] => {
  const map: Record<string, string[]> = {
    eating: ['mcdonald', 'tim hortons', 'starbucks', 'uber eats', 'ubereats', 'doordash', 'skipthedishes', 'a&w', 'subway', 'chipotle', 'pizza', 'sushi', 'restaurant', 'cafe', 'coffee', 'burger', 'white spot', 'earls', 'cactus club', 'freshii', 'wendy', 'popeyes', 'kfc', 'taco', 'pho', 'ramen', 'jugo juice', 'blenz', 'jj bean', 'nando'],
    drinks: ['liquor', 'bcl ', 'bc liquor', 'pub', 'brewing', 'brewery', 'taphouse', 'lounge', 'cabaret', 'bowling', 'cineplex', 'ticketmaster', 'stubhub', 'bar ', 'nightclub', 'commodore'],
    gas: ['esso', 'petro-can', 'petro can', 'petrocan', 'shell', 'chevron', 'husky', 'mobil', 'co-op gas', 'costco gas', 'pioneer', 'domo', 'save on gas', 'fas gas', 'gas bar'],
    lifestyle: ['nike', 'lululemon', 'golf', 'sport chek', 'amazon', 'amzn', 'zyn', 'vape', 'uniqlo', 'h&m', 'adidas', 'foot locker', 'zara', 'sporting life', 'aritzia', 'winners', 'old navy', 'hudson', 'best buy', 'apple.com', 'barber'],
    insurance: ['icbc', 'insurance'],
    ignore: ['payment thank you', 'payment received', 'paiement', 'online payment', 'transfer', 'e-transfer', 'payroll', 'pay deposit', 'deposit', 'wealthsimple', 'mortgage', 'interest charge'],
  };
  let i = 0;
  return Object.entries(map).flatMap(([cat, words]) => words.map((w) => r(w, cat, i++)));
};

export const makeDefaultState = (): AppState => ({
  version: SCHEMA_VERSION,
  settings: {
    paychequeAmount: 1650,
    paychequesPerMonth: 2,
    studentLoanPayment: 420,
    studentLoanMinimum: 420,
    emergencyMonthly: 700,
    wealthsimpleMonthly: 587,
    emergencyTarget: 5000,
    phaseOverride: 0,
    fhsaOpened: false,
    fhsaAnnualLimit: 8000,
    fhsaLifetimeLimit: 40000,
    tfsaRoom: 45500,
    efStartBalance: 0,
    wsValue: { FHSA: null, TFSA: null },
    wsValueUpdated: null,
    otherCash: 0,
    vehicleName: 'My car',
    odometerYearStart: {},
    abbyTrip: { from: 'Vancouver', to: 'Abbotsford', purpose: 'Weekly work drive', km: 140 },
    lastBackupAt: null,
  },
  categories: DEFAULT_CATEGORIES.map((c) => ({ ...c, keywords: [...c.keywords] })),
  entries: [],
  checkins: [],
  paycheques: [],
  debts: DEFAULT_DEBTS(),
  debtPayments: [],
  efTxns: [],
  wsContributions: [],
  checklist: [{ id: 'fhsa', text: 'Open FHSA before Dec 31, 2026', due: '2026-12-31', done: false }],
  trips: [],
  fillups: [],
  rules: DEFAULT_RULES(),
});

/** Merge a loaded/imported state over defaults so new fields always exist. */
export function hydrate(raw: unknown): AppState {
  const d = makeDefaultState();
  if (!raw || typeof raw !== 'object') return d;
  const s = raw as Partial<AppState>;
  const arr = <T,>(v: T[] | undefined, fb: T[]) => (Array.isArray(v) ? v : fb);
  return {
    version: SCHEMA_VERSION,
    settings: {
      ...d.settings,
      ...(s.settings ?? {}),
      wsValue: { ...d.settings.wsValue, ...(s.settings?.wsValue ?? {}) },
      abbyTrip: { ...d.settings.abbyTrip, ...(s.settings?.abbyTrip ?? {}) },
      odometerYearStart: { ...(s.settings?.odometerYearStart ?? {}) },
    },
    categories: arr(s.categories, d.categories),
    entries: arr(s.entries, []),
    checkins: arr(s.checkins, []),
    paycheques: arr(s.paycheques, []),
    debts: arr(s.debts, d.debts),
    debtPayments: arr(s.debtPayments, []),
    efTxns: arr(s.efTxns, []),
    wsContributions: arr(s.wsContributions, []),
    checklist: arr(s.checklist, d.checklist),
    trips: arr(s.trips, []),
    fillups: arr(s.fillups, []),
    rules: arr(s.rules, d.rules),
  };
}
