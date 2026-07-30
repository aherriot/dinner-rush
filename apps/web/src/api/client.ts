import createClient from "openapi-fetch";

import type { paths } from "./schema";

const FRONT_OF_HOUSE_URL = import.meta.env.VITE_FRONT_OF_HOUSE_URL ?? "http://localhost:8000";

let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export const api = createClient<paths>({ baseUrl: FRONT_OF_HOUSE_URL });

api.use({
  onRequest({ request }) {
    if (accessToken) {
      request.headers.set("Authorization", `Bearer ${accessToken}`);
    }
    return request;
  },
});
