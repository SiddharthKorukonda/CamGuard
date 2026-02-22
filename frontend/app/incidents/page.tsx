"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { AlertTriangle, ChevronRight, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { cn, severityColor, statusBadge, timeAgo, formatSeconds } from "@/lib/utils";
import { onWSEvent } from "@/lib/ws";

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [severityMin, setSeverityMin] = useState<number>(0);

  const fetchIncidents = async () => {
    try {
      const params: any = {};
      if (statusFilter) params.status = statusFilter;
      if (severityMin > 0) params.severity_min = severityMin;
      const data = await api.listIncidents(params);
      setIncidents(data);
    } catch {} finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchIncidents(); }, [statusFilter, severityMin]);
  useEffect(() => {
    const unsub = onWSEvent(() => fetchIncidents());
    const interval = setInterval(fetchIncidents, 5000);
    return () => { unsub(); clearInterval(interval); };
  }, [statusFilter, severityMin]);

  const getThreatInfo = (inc: any) => {
    const isHigh = inc.severity_current >= 4;
    return {
      level: isHigh ? "HIGH" : "MEDIUM",
      label: isHigh ? "Person on the floor" : "Person on the edge",
      color: isHigh ? "bg-red-100 text-red-800 border-red-200" : "bg-yellow-100 text-yellow-800 border-yellow-200",
      dotColor: isHigh ? "bg-red-500" : "bg-yellow-500",
    };
  };

  return (
    <AppShell>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Incidents</h2>
          <p className="text-sm text-hospital-muted">{incidents.length} total incidents</p>
        </div>
        <div className="flex gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input-field w-auto text-sm"
          >
            <option value="">All Status</option>
            <option value="ACTIVE">Active</option>
            <option value="ACKED">Acknowledged</option>
            <option value="CLOSED">Closed</option>
          </select>
          <select
            value={severityMin}
            onChange={(e) => setSeverityMin(Number(e.target.value))}
            className="input-field w-auto text-sm"
          >
            <option value={0}>All Severity</option>
            <option value={3}>Sev 3+</option>
            <option value={4}>Sev 4+</option>
            <option value={5}>Sev 5</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="card flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
        </div>
      ) : incidents.length === 0 ? (
        <div className="card text-center py-16 text-hospital-muted">
          <AlertTriangle className="w-12 h-12 mx-auto mb-3 text-slate-300" />
          <p className="text-lg">No incidents found</p>
          <p className="text-sm mt-1">Incidents will appear here when detected by cameras</p>
        </div>
      ) : (
        <div className="space-y-3">
          {incidents.map((inc) => {
            const sb = statusBadge(inc.status);
            const threat = getThreatInfo(inc);
            return (
              <Link key={inc.incident_id} href={`/incidents/${inc.incident_id}`}>
                <div className={cn(
                  "card-compact hover:shadow-md transition-shadow cursor-pointer flex items-center gap-4 border-l-4",
                  threat.level === "HIGH" ? "border-l-red-500" : "border-l-yellow-500"
                )}>
                  <div className={cn("w-12 h-12 rounded-xl flex items-center justify-center text-white font-bold text-lg", severityColor(inc.severity_current))}>
                    {inc.severity_current}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={cn("badge border", threat.color)}>
                        <span className={cn("w-2 h-2 rounded-full inline-block mr-1", threat.dotColor)} />
                        {threat.label}
                      </span>
                      <span className={cn("badge", sb.bg)}>{sb.text}</span>
                    </div>
                    <p className="text-xs text-hospital-muted mt-1 truncate">
                      Camera: {inc.camera_id?.slice(0, 16)} • Time down: {formatSeconds(inc.time_down_s)} • {timeAgo(inc.created_at)}
                    </p>
                    {inc.reasons_current?.length > 0 && (
                      <p className="text-xs text-slate-500 mt-1 truncate">
                        {inc.reasons_current[0]}
                      </p>
                    )}
                  </div>
                  <ChevronRight className="w-5 h-5 text-slate-400 flex-shrink-0" />
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}
