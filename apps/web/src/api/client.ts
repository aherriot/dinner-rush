import createClient from "openapi-fetch";

import type { paths } from "./schema";

const GATEWAY_URL = import.meta.env.VITE_GATEWAY_URL ?? "http://localhost:8000";

let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export const api = createClient<paths>({ baseUrl: GATEWAY_URL });

api.use({
  onRequest({ request }) {
    if (accessToken) {
      request.headers.set("Authorization", `Bearer ${accessToken}`);
    }
    return request;
  },
});
