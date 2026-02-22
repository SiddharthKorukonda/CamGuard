"use client";

const AUTH_KEY = "camguard_auth";
const ONBOARDED_KEY = "camguard_onboarded";

export interface AuthUser {
  email: string;
  name: string;
}

export function getUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(AUTH_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function login(email: string, _pin: string): AuthUser {
  const name = email.split("@")[0].replace(/[._]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  const user: AuthUser = { email, name };
  localStorage.setItem(AUTH_KEY, JSON.stringify(user));
  return user;
}

export function logout() {
  localStorage.removeItem(AUTH_KEY);
  localStorage.removeItem(ONBOARDED_KEY);
}

export function isOnboarded(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(ONBOARDED_KEY) === "true";
}

export function setOnboarded() {
  localStorage.setItem(ONBOARDED_KEY, "true");
}

export function clearSessionOnLoad() {
  if (typeof window === "undefined") return;
  const loaded = sessionStorage.getItem("camguard_session_init");
  if (!loaded) {
    localStorage.removeItem(AUTH_KEY);
    localStorage.removeItem(ONBOARDED_KEY);
    sessionStorage.setItem("camguard_session_init", "true");
  }
}
