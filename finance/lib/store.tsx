'use client';
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import type { AppState } from './types';
import { STORAGE_KEY, hydrate, makeDefaultState } from './defaults';

interface Ctx {
  state: AppState;
  /** Mutate a draft copy; the result is saved to localStorage automatically. */
  update: (fn: (draft: AppState) => void) => void;
  replace: (next: AppState) => void;
  toast: (msg: string) => void;
  saveError: string | null;
}

const StoreCtx = createContext<Ctx | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AppState | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    let loaded: AppState;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      loaded = raw ? hydrate(JSON.parse(raw)) : makeDefaultState();
    } catch {
      loaded = makeDefaultState();
    }
    setState(loaded);
    // ask the browser not to evict our data (Safari otherwise may after 7 days unused)
    try { navigator.storage?.persist?.(); } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    if (!state) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      setSaveError(null);
    } catch (e) {
      setSaveError('Could not save to this browser. Export a backup now.');
    }
  }, [state]);

  const update = useCallback((fn: (d: AppState) => void) => {
    setState((prev) => {
      if (!prev) return prev;
      const draft = structuredClone(prev);
      fn(draft);
      return draft;
    });
  }, []);

  const replace = useCallback((next: AppState) => setState(hydrate(next)), []);

  const toast = useCallback((msg: string) => {
    setToastMsg(msg);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setToastMsg(null), 2200);
  }, []);

  if (!state) return <div className="boot" aria-busy="true" />;
  return (
    <StoreCtx.Provider value={{ state, update, replace, toast, saveError }}>
      {children}
      <div className={`toast ${toastMsg ? 'show' : ''}`} role="status" aria-live="polite">{toastMsg}</div>
    </StoreCtx.Provider>
  );
}

export function useStore() {
  const c = useContext(StoreCtx);
  if (!c) throw new Error('useStore outside provider');
  return c;
}
