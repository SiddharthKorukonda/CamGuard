"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import {
  Camera,
  AlertTriangle,
  Activity,
  Clock,
  ChevronRight,
  Loader2,
  Play,
  Globe,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn, severityColor, statusBadge, timeAgo, LANGUAGES } from "@/lib/utils";
import { getUser } from "@/lib/auth";
import { showToast } from "@/components/Toast";
import { onWSEvent } from "@/lib/ws";

const UI_STRINGS = {
  welcome: "Welcome back,",
  systemMonitoring: "All systems monitoring.",
  camerasActive: "camera(s) active.",
  cameras: "Cameras",
  activeIncidents: "Active Incidents",
  avgSeverity: "Avg Severity",
  totalIncidents: "Total Incidents",
  camerasTitle: "Cameras",
  noCameras: "No cameras registered yet",
  noCamerasHint: "Go to the Cameras page to add a camera",
  activeIncidentsTitle: "Active Incidents",
  noActiveIncidents: "No active incidents",
  time: "Time",
  camera: "Camera",
  threat: "Threat",
  severity: "Severity",
  status: "Status",
  actions: "Actions",
  open: "Open",
  risk: "Risk",
  personOnFloor: "Person on the floor",
  personOnEdge: "Person on the edge",
  preventionDemo: "Prevention Demo",
  fallDemo: "Fall Demo",
};

export default function DashboardPage() {
  const [cameras, setCameras] = useState<any[]>([]);
  const [incidents, setIncidents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [demoLoading, setDemoLoading] = useState("");
  const [selectedLang, setSelectedLang] = useState("en");
  const [t, setT] = useState<Record<string, string>>(UI_STRINGS);
  const [translating, setTranslating] = useState(false);
  const user = getUser();

  const fetchData = async () => {
    try {
      const [cams, incs] = await Promise.all([
        api.listCameras().catch(() => []),
        api.listIncidents().catch(() => []),
      ]);
      setCameras(cams);
      setIncidents(incs);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const unsub = onWSEvent(() => fetchData());
    const interval = setInterval(fetchData, 10000);
    return () => { unsub(); clearInterval(interval); };
  }, []);

  const activeIncidents = incidents.filter((i) => i.status === "ACTIVE");
  const avgSeverity = activeIncidents.length
    ? (activeIncidents.reduce((s, i) => s + i.severity_current, 0) / activeIncidents.length).toFixed(1)
    : "0";

  const runDemo = async (type: "prevention" | "fall") => {
    setDemoLoading(type);
    try {
      if (type === "prevention") await api.demoPrevention();
      else await api.demoFall();
      showToast({ type: "success", title: `${type} demo triggered` });
      fetchData();
    } catch (e: any) {
      showToast({ type: "error", title: "Demo failed", message: e.message });
    } finally {
      setDemoLoading("");
    }
  };

  const handleLanguageChange = async (lang: string) => {
    setSelectedLang(lang);
    if (lang === "en") {
      setT(UI_STRINGS);
      return;
    }
    setTranslating(true);
    try {
      const keys = Object.keys(UI_STRINGS);
      const values = Object.values(UI_STRINGS);
      const result = await api.translateBatch(values, LANGUAGES.find((l) => l.code === lang)?.label || lang);
      const translated: Record<string, string> = {};
      keys.forEach((key, i) => {
        translated[key] = result.translations[i] || UI_STRINGS[key as keyof typeof UI_STRINGS];
      });
      setT(translated);
      showToast({ type: "success", title: "Page translated" });
    } catch {
      showToast({ type: "error", title: "Translation failed" });
    } finally {
      setTranslating(false);
    }
  };

  return (
    <AppShell>
      {/* Welcome Banner */}
      <div className="card bg-gradient-to-r from-brand-600 to-brand-700 text-white mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold">{t.welcome} {user?.name || "Caregiver"}</h2>
            <p className="text-brand-100 mt-1">{t.systemMonitoring} {cameras.length} {t.camerasActive}{translating ? " ..." : ""}</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Globe className="w-4 h-4 text-white/70 absolute left-2 top-1/2 -translate-y-1/2 pointer-events-none" />
              <select
                value={selectedLang}
                onChange={(e) => handleLanguageChange(e.target.value)}
                disabled={translating}
                className="pl-7 pr-3 py-1.5 text-xs rounded-lg bg-white/20 text-white border-0 appearance-none cursor-pointer hover:bg-white/30 transition-colors disabled:opacity-50"
              >
                {LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code} className="text-slate-900">
                    {l.native}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: t.cameras, value: cameras.length, icon: Camera, color: "text-blue-600 bg-blue-50" },
          { label: t.activeIncidents, value: activeIncidents.length, icon: AlertTriangle, color: "text-red-600 bg-red-50" },
          { label: t.avgSeverity, value: avgSeverity, icon: Activity, color: "text-orange-600 bg-orange-50" },
          { label: t.totalIncidents, value: incidents.length, icon: Clock, color: "text-slate-600 bg-slate-50" },
        ].map((stat) => (
          <div key={stat.label} className="card-compact flex items-center gap-4">
            <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center", stat.color)}>
              <stat.icon className="w-5 h-5" />
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900">{stat.value}</p>
              <p className="text-xs text-hospital-muted">{stat.label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Camera Tiles */}
      <h3 className="text-lg font-semibold text-slate-900 mb-3">{t.camerasTitle}</h3>
      {loading ? (
        <div className="card flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
        </div>
      ) : cameras.length === 0 ? (
        <div className="card text-center py-12 text-hospital-muted">
          <Camera className="w-10 h-10 mx-auto mb-3 text-slate-300" />
          <p>{t.noCameras}</p>
          <p className="text-sm mt-1">{t.noCamerasHint}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          {cameras.map((cam) => {
            const camIncident = activeIncidents.find((i) => i.camera_id === cam.id);
            return (
              <Link key={cam.id} href={`/cameras/${cam.id}`}>
                <div className="card-compact hover:shadow-md transition-shadow cursor-pointer">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className={cn("w-2.5 h-2.5 rounded-full", cam.status === "online" ? "bg-green-500" : "bg-gray-400")} />
                      <span className="font-medium text-sm">{cam.name}</span>
                    </div>
                    <span className="text-xs text-hospital-muted">{cam.room_type}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="text-xs text-hospital-muted">
                      {t.risk}: <span className={cn("font-semibold", cam.risk_score > 0.7 ? "text-red-600" : cam.risk_score > 0.3 ? "text-orange-500" : "text-green-600")}>
                        {(cam.risk_score * 100).toFixed(0)}%
                      </span>
                    </div>
                    {camIncident && (
                      <span className={cn("badge text-white", severityColor(camIncident.severity_current))}>
                        Sev {camIncident.severity_current}
                      </span>
                    )}
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {/* Active Incidents Table */}
      <h3 className="text-lg font-semibold text-slate-900 mb-3">{t.activeIncidentsTitle}</h3>
      {activeIncidents.length === 0 ? (
        <div className="card text-center py-8 text-hospital-muted">
          <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-slate-300" />
          <p>{t.noActiveIncidents}</p>
        </div>
      ) : (
        <div className="card-compact overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hospital-border text-left text-xs text-hospital-muted uppercase tracking-wider">
                <th className="pb-3 pl-4">{t.time}</th>
                <th className="pb-3">{t.camera}</th>
                <th className="pb-3">{t.threat}</th>
                <th className="pb-3">{t.severity}</th>
                <th className="pb-3">{t.status}</th>
                <th className="pb-3 pr-4">{t.actions}</th>
              </tr>
            </thead>
            <tbody>
              {activeIncidents.map((inc) => {
                const sb = statusBadge(inc.status);
                const isHigh = inc.severity_current >= 4;
                const threatLabel = isHigh ? t.personOnFloor : t.personOnEdge;
                const threatColor = isHigh ? "bg-red-100 text-red-800" : "bg-yellow-100 text-yellow-800";
                return (
                  <tr key={inc.incident_id} className="border-b border-hospital-border last:border-0 hover:bg-slate-50">
                    <td className="py-3 pl-4 text-xs text-hospital-muted">{timeAgo(inc.created_at)}</td>
                    <td className="py-3 text-xs">{inc.camera_id?.slice(0, 12)}</td>
                    <td className="py-3">
                      <span className={cn("badge", threatColor)}>{threatLabel}</span>
                    </td>
                    <td className="py-3">
                      <span className={cn("badge text-white", severityColor(inc.severity_current))}>
                        Sev {inc.severity_current}
                      </span>
                    </td>
                    <td className="py-3"><span className={cn("badge", sb.bg)}>{sb.text}</span></td>
                    <td className="py-3 pr-4">
                      <Link
                        href={`/incidents/${inc.incident_id}`}
                        className="text-brand-600 hover:text-brand-700 text-xs font-medium flex items-center gap-1"
                      >
                        {t.open} <ChevronRight className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Demo buttons - subtle, bottom-left */}
      <div className="fixed bottom-4 left-[17rem] z-20 flex gap-2">
        <button
          onClick={() => runDemo("prevention")}
          disabled={!!demoLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-500 hover:text-slate-700 bg-white/80 hover:bg-white border border-slate-200 rounded-lg shadow-sm transition-all"
        >
          {demoLoading === "prevention" ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
          Prevention Demo
        </button>
        <button
          onClick={() => runDemo("fall")}
          disabled={!!demoLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-500 hover:text-red-600 bg-white/80 hover:bg-white border border-slate-200 rounded-lg shadow-sm transition-all"
        >
          {demoLoading === "fall" ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
          Fall Demo
        </button>
      </div>
    </AppShell>
  );
}
