"use client";

import { useState, useEffect, useCallback } from "react";
import { X, AlertTriangle, CheckCircle, Info } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ToastMessage {
  id: string;
  type: "info" | "success" | "warning" | "error";
  title: string;
  message?: string;
}

let addToastFn: ((t: Omit<ToastMessage, "id">) => void) | null = null;

export function showToast(t: Omit<ToastMessage, "id">) {
  addToastFn?.(t);
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((t: Omit<ToastMessage, "id">) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev.slice(-4), { ...t, id }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((x) => x.id !== id));
    }, 5000);
  }, []);

  useEffect(() => {
    addToastFn = addToast;
    return () => { addToastFn = null; };
  }, [addToast]);

  const icons = {
    info: Info,
    success: CheckCircle,
    warning: AlertTriangle,
    error: AlertTriangle,
  };

  const colors = {
    info: "bg-blue-50 border-blue-200 text-blue-800",
    success: "bg-green-50 border-green-200 text-green-800",
    warning: "bg-yellow-50 border-yellow-200 text-yellow-800",
    error: "bg-red-50 border-red-200 text-red-800",
  };

  return (
    <div className="fixed top-4 right-[340px] z-50 space-y-2 w-80">
      {toasts.map((t) => {
        const Icon = icons[t.type];
        return (
          <div
            key={t.id}
            className={cn("flex items-start gap-3 p-3 rounded-xl border shadow-lg animate-in slide-in-from-right", colors[t.type])}
          >
            <Icon className="w-5 h-5 mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium">{t.title}</p>
              {t.message && <p className="text-xs mt-0.5 opacity-80">{t.message}</p>}
            </div>
            <button
              onClick={() => setToasts((p) => p.filter((x) => x.id !== t.id))}
              className="opacity-60 hover:opacity-100"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
