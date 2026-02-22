"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Sidebar from "./Sidebar";
import AssistantPanel from "./AssistantPanel";
import { ToastContainer, showToast } from "./Toast";
import { getUser, isOnboarded, clearSessionOnLoad } from "@/lib/auth";
import { connectWS, onWSEvent, disconnectWS } from "@/lib/ws";

export default function AppShell({
  children,
  incidentId,
  cameraId,
  currentPlan,
  reasons,
  onTranslate,
  onReadAloud,
  onAcknowledge,
  onFalseAlarm,
  onEscalate,
}: {
  children: React.ReactNode;
  incidentId?: string;
  cameraId?: string;
  currentPlan?: any;
  reasons?: string[];
  onTranslate?: (lang: string) => void;
  onReadAloud?: () => void;
  onAcknowledge?: () => void;
  onFalseAlarm?: () => void;
  onEscalate?: () => void;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [darkMode, setDarkMode] = useState(false);

  useEffect(() => {
    clearSessionOnLoad();
  }, []);

  useEffect(() => {
    const publicPaths = ["/login", "/onboarding"];
    if (publicPaths.includes(pathname)) return;

    if (!getUser()) {
      router.push("/login");
      return;
    }
    if (!isOnboarded()) {
      router.push("/onboarding");
      return;
    }
  }, [pathname, router]);

  useEffect(() => {
    connectWS();
    const unsub = onWSEvent((event) => {
      if (event.type === "ACK_RECEIVED") {
        showToast({ type: "success", title: "Incident Acknowledged" });
      }
    });
    return () => { unsub(); disconnectWS(); };
  }, []);

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [darkMode]);

  const publicPaths = ["/login", "/onboarding"];
  if (publicPaths.includes(pathname)) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="ml-64 mr-80 flex-1 min-h-screen">
        <div className="p-6 max-w-[1200px] mx-auto">{children}</div>
      </main>
      <AssistantPanel
        incidentId={incidentId}
        cameraId={cameraId}
        currentPlan={currentPlan}
        reasons={reasons}
        onTranslate={onTranslate}
        onReadAloud={onReadAloud}
        onAcknowledge={onAcknowledge}
        onFalseAlarm={onFalseAlarm}
        onEscalate={onEscalate}
      />
      <ToastContainer />
    </div>
  );
}
