const KEY = "p7_session_id";

export const saveSession = (id: string): void =>
  localStorage.setItem(KEY, id);

export const loadSession = (): string | null =>
  localStorage.getItem(KEY);

export const clearSession = (): void =>
  localStorage.removeItem(KEY);
