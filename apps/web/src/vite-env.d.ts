/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_FRONT_OF_HOUSE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
