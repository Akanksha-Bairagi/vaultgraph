import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./lib/api.ts";

export interface Async<T> { data: T | null; error: string | null; loading: boolean; reload: () => void }

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []): Async<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  useEffect(() => {
    let alive = true;
    setLoading(true);
    fnRef.current().then(
      (d) => { if (alive) { setData(d); setError(null); setLoading(false); } },
      (e: unknown) => { if (alive) { setError(e instanceof ApiError ? e.message : "Something went wrong."); setLoading(false); } },
    );
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, ...deps]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload };
}

export const messageOf = (e: unknown): string => (e instanceof ApiError ? e.message : "Something went wrong. Please try again.");

export type Route = "/" | "/ask" | "/documents" | "/graph" | "/people" | "/audit";
const ROUTES: Route[] = ["/", "/ask", "/documents", "/graph", "/people", "/audit"];
const parse = (): Route => {
  const h = window.location.hash.replace(/^#/, "") || "/";
  return (ROUTES as string[]).includes(h) ? (h as Route) : "/";
};
export function navigate(r: Route) { window.location.hash = r; }
export function useRoute(): Route {
  const [r, setR] = useState<Route>(parse);
  useEffect(() => {
    const on = () => setR(parse());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return r;
}
