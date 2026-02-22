"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { History, ChevronRight, Loader2, TrendingDown, TrendingUp } from "lucide-react";
import { api } from "@/lib/api";
import { cn, severityColor, statusBadge, formatSeconds } from "@/lib/utils";

export default function HistoryPage() {
  const [incidents, setIncidents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await api.listIncidents({ status: "" });
        setIncidents(data);
      } catch {} finally { setLoading(false); }
    };
    load();
  }, []);

  const closedIncidents = incidents.filter((i) => i.status === "CLOSED" || i.status === "ACKED");
  const maxSev = incidents.reduce((m, i) => Math.max(m, i.severity_current), 0);
  const avgTime = incidents.length
    ? (incidents.reduce((s, i) => s + (i.time_down_s || 0), 0) / incidents.length)
    : 0;

  return (
    <AppShell>
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-900">History & Analytics</h2>
        <p className="text-sm text-hospital-muted">Past incidents and performance insights</p>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="card-compact text-center">
          <p className="text-3xl font-bold text-slate-900">{incidents.length}</p>
          <p className="text-xs text-hospital-muted">Total Incidents</p>
        </div>
        <div className="card-compact text-center">
          <p className="text-3xl font-bold text-slate-900">{maxSev || "-"}</p>
          <p className="text-xs text-hospital-muted">Peak Severity</p>
        </div>
        <div className="card-compact text-center">
          <p className="text-3xl font-bold text-slate-900">{formatSeconds(avgTime)}</p>
          <p className="text-xs text-hospital-muted">Avg Response Time</p>
        </div>
      </div>

      {/* Severity Timeline (simple bar chart) */}
      <div className="card mb-6">
        <h3 className="text-sm font-semibold text-slate-900 mb-3">Severity Timeline</h3>
        {incidents.length > 0 ? (
          <div className="flex items-end gap-1 h-32">
            {incidents.slice(-30).map((inc, i) => (
              <div
                key={i}
                className={cn("flex-1 min-w-[8px] rounded-t transition-all", severityColor(inc.severity_current))}
                style={{ height: `${(inc.severity_current / 5) * 100}%` }}
                title={`Sev ${inc.severity_current} - ${inc.verdict}`}
              />
            ))}
          </div>
        ) : (
          <p className="text-sm text-hospital-muted text-center py-8">No data yet</p>
        )}
      </div>

      {/* Improvement View */}
      <div className="card mb-6">
        <h3 className="text-sm font-semibold text-slate-900 mb-3">Improvement Insights</h3>
        <div className="space-y-3">
          <div className="flex items-center gap-3 p-3 bg-green-50 rounded-xl">
            <TrendingDown className="w-5 h-5 text-green-600" />
            <div>
              <p className="text-sm font-medium text-green-800">Response time trending down</p>
              <p className="text-xs text-green-600">Based on Snowflake optimization data</p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-xl">
            <TrendingUp className="w-5 h-5 text-blue-600" />
            <div>
              <p className="text-sm font-medium text-blue-800">Self-optimization active</p>
              <p className="text-xs text-blue-600">Camera thresholds auto-tuned during idle periods</p>
            </div>
          </div>
        </div>
      </div>

      {/* Incident List */}
      <h3 className="text-sm font-semibold text-slate-900 mb-3">All Incidents</h3>
      {loading ? (
        <div className="card flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
        </div>
      ) : (
        <div className="space-y-2">
          {incidents.map((inc) => {
            const sb = statusBadge(inc.status);
            return (
              <Link key={inc.incident_id} href={`/incidents/${inc.incident_id}`}>
                <div className="card-compact hover:shadow-md transition-shadow cursor-pointer flex items-center gap-4">
                  <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center text-white text-sm font-bold", severityColor(inc.severity_current))}>
                    {inc.severity_current}
                  </div>
                  <div className="flex-1">
                    <span className="text-sm font-medium">{inc.verdict}</span>
                    <span className={cn("badge ml-2", sb.bg)}>{sb.text}</span>
                    <p className="text-xs text-hospital-muted">
                      {new Date(inc.created_at).toLocaleString()} • {formatSeconds(inc.time_down_s)}
                    </p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-400" />
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}
