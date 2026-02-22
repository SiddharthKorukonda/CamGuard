import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function severityColor(level: number): string {
  const colors: Record<number, string> = {
    1: "bg-green-500",
    2: "bg-yellow-500",
    3: "bg-orange-500",
    4: "bg-red-500",
    5: "bg-red-700",
  };
  return colors[level] || "bg-gray-400";
}

export function severityTextColor(level: number): string {
  const colors: Record<number, string> = {
    1: "text-green-600",
    2: "text-yellow-600",
    3: "text-orange-600",
    4: "text-red-600",
    5: "text-red-800",
  };
  return colors[level] || "text-gray-500";
}

export function severityBg(level: number): string {
  const colors: Record<number, string> = {
    1: "bg-green-50 border-green-200",
    2: "bg-yellow-50 border-yellow-200",
    3: "bg-orange-50 border-orange-200",
    4: "bg-red-50 border-red-200",
    5: "bg-red-100 border-red-300",
  };
  return colors[level] || "bg-gray-50 border-gray-200";
}

export function statusBadge(status: string): { bg: string; text: string } {
  switch (status?.toUpperCase()) {
    case "ACTIVE":
      return { bg: "bg-red-100 text-red-800", text: "Active" };
    case "ACKED":
      return { bg: "bg-blue-100 text-blue-800", text: "Acknowledged" };
    case "CLOSED":
      return { bg: "bg-gray-100 text-gray-600", text: "Closed" };
    default:
      return { bg: "bg-gray-100 text-gray-500", text: status || "Unknown" };
  }
}

export function timeAgo(ts: string): string {
  const diff = (Date.now() - new Date(ts).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function formatSeconds(s: number): string {
  if (s < 60) return `${Math.floor(s)}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${Math.floor(s % 60)}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}

export const LANGUAGES = [
  { code: "en", label: "English", native: "English" },
  { code: "es", label: "Spanish", native: "Español" },
  { code: "fr", label: "French", native: "Français" },
  { code: "zh", label: "Chinese", native: "中文" },
  { code: "ar", label: "Arabic", native: "العربية" },
  { code: "hi", label: "Hindi", native: "हिन्दी" },
  { code: "pt", label: "Portuguese", native: "Português" },
  { code: "ko", label: "Korean", native: "한국어" },
  { code: "ja", label: "Japanese", native: "日本語" },
  { code: "de", label: "German", native: "Deutsch" },
  { code: "it", label: "Italian", native: "Italiano" },
  { code: "ru", label: "Russian", native: "Русский" },
  { code: "tr", label: "Turkish", native: "Türkçe" },
  { code: "vi", label: "Vietnamese", native: "Tiếng Việt" },
  { code: "th", label: "Thai", native: "ไทย" },
  { code: "pl", label: "Polish", native: "Polski" },
  { code: "nl", label: "Dutch", native: "Nederlands" },
  { code: "sv", label: "Swedish", native: "Svenska" },
  { code: "he", label: "Hebrew", native: "עברית" },
  { code: "id", label: "Indonesian", native: "Bahasa Indonesia" },
];
