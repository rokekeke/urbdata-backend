const API_BASE_URL_ENV = "NEXT_PUBLIC_API_BASE_URL";

export class RuntimeConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RuntimeConfigError";
  }
}

/**
 * Validates and normalizes the public backend URL without making a request.
 * Keep the raw value injectable so this behavior can be unit-tested in FA-008.
 */
export function resolveApiBaseUrl(rawValue?: string): string {
  const value = rawValue?.trim();

  if (!value) {
    throw new RuntimeConfigError(
      `${API_BASE_URL_ENV} não foi configurada. Copie .env.example para .env.local e informe a URL pública do backend.`,
    );
  }

  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new RuntimeConfigError(
      `${API_BASE_URL_ENV} deve ser uma URL absoluta, por exemplo http://localhost:8000.`,
    );
  }

  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new RuntimeConfigError(`${API_BASE_URL_ENV} deve usar o protocolo http ou https.`);
  }

  if (url.username || url.password) {
    throw new RuntimeConfigError(
      `${API_BASE_URL_ENV} é pública e não pode conter usuário, senha ou credenciais.`,
    );
  }

  if (url.search || url.hash) {
    throw new RuntimeConfigError(`${API_BASE_URL_ENV} não pode conter query string ou fragmento.`);
  }

  url.pathname = url.pathname.replace(/\/+$/, "");
  return url.toString().replace(/\/+$/, "");
}

/** Reads the statically exposed Next.js environment variable. */
export function getApiBaseUrl(): string {
  return resolveApiBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL);
}
