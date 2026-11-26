export type ISODate = string; // YYYY-MM-DD, local time

export interface Category {
  id: string;
  name: string;
  emoji: string;
  color: string;
  /** Budget amount, interpreted per `period`. */
  amount: number;
  period: 'week' | 'month';
  /** Fixed bills (e.g. car insurance) are tracked monthly only. */
  fixed: boolean;
  /** Excluded from budgets and totals (transfers, card payments, income). */
  ignore?: boolean;
  /** Comma-free list of words used to guess this category when typing a note. */
  keywords: string[];
}

export interface Entry {
  id: string;
  date: ISODate;
  amount: number;
  categoryId: string;
  note: string;
  source: 'manual' | 'import';
  account?: BankAccount;
  /** Raw statement description (imports only). */
  description?: string;
  /** Manual entry that a statement line was matched to. */
  matchedManualId?: string;
  /** Statement line that confirmed this manual entry (manual only). */
  matchedImportId?: string;
  fillupId?: string;
  createdAt: number;
}

export type BankAccount = 'RBC' | 'Tangerine' | 'Amex';

export interface SplitItem {
  key: string;
  label: string;
  amount: number;
  done: boolean;
  kind: 'bill' | 'debt' | 'ef' | 'ws';
  debtId?: string;
  wsAccount?: WsAccount;
  /** id of the payment / deposit / contribution created when checked */
  recordId?: string;
}

export interface Paycheque {
  id: string;
  date: ISODate;
  amount: number;
  note: string;
  phase: 1 | 2 | 3;
  split: SplitItem[];
  createdAt: number;
}

export interface Debt {
  id: string;
  name: string;
  kind: 'card' | 'loan';
  apr: number;
  color: string;
  /** Balance when you started tracking (for the progress bar). */
  originalBalance: number;
  /** Last balance you confirmed, and when. Payments after this reduce it. */
  balance: number;
  balanceSetAt: number;
  deadline?: ISODate;
  note: string;
}

export interface DebtPayment {
  id: string;
  debtId: string;
  date: ISODate;
  amount: number;
  note: string;
  paychequeId?: string;
  createdAt: number;
}

export interface EfTxn {
  id: string;
  date: ISODate;
  amount: number; // + deposit, - withdrawal
  note: string;
  paychequeId?: string;
  createdAt: number;
}

export type WsAccount = 'FHSA' | 'TFSA';

export interface WsContribution {
  id: string;
  date: ISODate;
  account: WsAccount;
  amount: number;
  note: string;
  paychequeId?: string;
  createdAt: number;
}

export interface ChecklistItem {
  id: string;
  text: string;
  due?: ISODate;
  done: boolean;
}

export interface Trip {
  id: string;
  date: ISODate;
  from: string;
  to: string;
  purpose: string;
  odoStart?: number;
  odoEnd?: number;
  km: number;
  business: boolean;
  createdAt: number;
}

export interface Fillup {
  id: string;
  date: ISODate;
  station: string;
  litres: number;
  amount: number;
  odometer?: number;
  entryId?: string;
  createdAt: number;
}

export interface Rule {
  id: string;
  match: string; // case-insensitive "contains"
  categoryId: string;
}

export interface Settings {
  paychequeAmount: number;
  paychequesPerMonth: number;
  studentLoanPayment: number;
  studentLoanMinimum: number;
  emergencyMonthly: number;
  wealthsimpleMonthly: number;
  emergencyTarget: number;
  phaseOverride: 0 | 1 | 2 | 3; // 0 = auto
  fhsaOpened: boolean;
  fhsaAnnualLimit: number;
  fhsaLifetimeLimit: number;
  tfsaRoom: number;
  efStartBalance: number;
  wsValue: Record<WsAccount, number | null>;
  wsValueUpdated: ISODate | null;
  otherCash: number;
  vehicleName: string;
  odometerYearStart: Record<string, number>; // year -> odometer on Jan 1
  abbyTrip: { from: string; to: string; purpose: string; km: number };
  lastBackupAt: number | null;
}

export interface AppState {
  version: number;
  settings: Settings;
  categories: Category[];
  entries: Entry[];
  checkins: ISODate[]; // days marked as logged (incl. "nothing today")
  paycheques: Paycheque[];
  debts: Debt[];
  debtPayments: DebtPayment[];
  efTxns: EfTxn[];
  wsContributions: WsContribution[];
  checklist: ChecklistItem[];
  trips: Trip[];
  fillups: Fillup[];
  rules: Rule[];
}
