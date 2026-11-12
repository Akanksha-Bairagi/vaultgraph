import { createClient } from "./api.ts";

/** Single shared API client. The JWT lives in sessionStorage (cleared when the tab closes); it is only ever sent
 *  to this same origin. React escapes all rendered text and the server sends a strict CSP, which limits XSS risk. */
export const api = createClient({
  storage: typeof sessionStorage !== "undefined" ? sessionStorage : undefined,
  onUnauthorized: () => { if (typeof window !== "undefined") window.dispatchEvent(new Event("vg:unauthorized")); },
});
