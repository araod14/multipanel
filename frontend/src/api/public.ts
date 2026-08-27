import axios from "axios";

import type { PublicResults } from "./types";

// A bare axios call on purpose: the shared client in ./client.ts attaches a Bearer
// header and, on a 401, redirects to /login. An anonymous visitor with a stale token
// left in localStorage would otherwise be bounced off a page that needs no login.
export const publicApi = {
  results: async (): Promise<PublicResults> =>
    (await axios.get<PublicResults>("/api/public/results")).data,
};
