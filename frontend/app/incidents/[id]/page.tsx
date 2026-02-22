"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import {
  AlertTriangle, CheckCircle, XCircle, Phone, ArrowUpRight,
  Globe, Volume2, Pause, Clock, Shield, Activity,
  ChevronDown, Loader2, Image as ImageIcon,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn, severityColor, severityBg, severityTextColor, statusBadge, formatSeconds, LANGUAGES } from "@/lib/utils";
import { showToast } from "@/components/Toast";
import { onWSEvent } from "@/lib/ws";

export default function IncidentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [incident, setIncident] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [plans, setPlans] = useState<any[]>([]);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [frames, setFrames] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  const [translatedText, setTranslatedText] = useState<string>("");
  const [translatedLang, setTranslatedLang] = useState("");
  const [translating, setTranslating] = useState(false);
  const [ttsLoading, setTtsLoading] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [translations, setTranslations] = useState<Record<string, string>>({});
  const [actionLoading, setActionLoading] = useState("");

  const audioRef = useRef<HTMLAudioElement>(null);

  const fetchAll = useCallback(async () => {
    if (!id) return;
    try {
      const [inc, sum, pls, tl, fr] = await Promise.all([
        api.getIncident(id).catch(() => null),
        api.getIncidentSummary(id).catch(() => null),
        api.getIncidentPlan(id).catch(() => []),
        api.getIncidentTimeline(id).catch(() => []),
        api.getIncidentFrames(id).catch(() => ({ frames_b64: [] })),
      ]);
      if (inc) setIncident(inc);
      if (sum) setSummary(sum);
      setPlans(pls);
      setTimeline(tl);
      setFrames(fr?.frames_b64 || []);
    } catch {} finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchAll();
    const unsub = onWSEvent((ev) => {
      if (ev.incident_id === id) fetchAll();
    });
    const interval = setInterval(fetchAll, 5000);
    return () => { unsub(); clearInterval(interval); };
  }, [id, fetchAll]);

  const handleAck = async () => {
    setActionLoading("ack");
    try {
      await api.ackIncident(id);
      showToast({ type: "success", title: "Incident acknowledged" });
      fetchAll();
    } catch (e: any) {
      showToast({ type: "error", title: "Acknowledge failed", message: e.message });
    } finally { setActionLoading(""); }
  };

  const handleFalseAlarm = async () => {
    if (!confirm("Mark this incident as a false alarm?")) return;
    setActionLoading("false");
    try {
      await api.falseAlarm(id);
      showToast({ type: "success", title: "Marked as false alarm" });
      fetchAll();
    } catch (e: any) {
      showToast({ type: "error", title: "Failed", message: e.message });
    } finally { setActionLoading(""); }
  };

  const handleTranslate = async (lang: string) => {
    if (translations[lang]) {
      setTranslatedText(translations[lang]);
      setTranslatedLang(lang);
      return;
    }
    setTranslating(true);
    try {
      const res = await api.translateIncident(id, lang);
      setTranslations((prev) => ({ ...prev, [lang]: res.translated_text }));
      setTranslatedText(res.translated_text);
      setTranslatedLang(lang);
      showToast({ type: "success", title: `Translated to ${lang}` });
    } catch (e: any) {
      showToast({ type: "error", title: "Translation failed", message: e.message });
    } finally { setTranslating(false); }
  };

  const handleTTS = async () => {
    setTtsLoading(true);
    try {
      const text = translatedText || summary?.summary_text || "";
      const blob = await api.ttsIncident(id, text || undefined);
      const url = URL.createObjectURL(blob);
      if (audioRef.current) {
        audioRef.current.src = url;
        audioRef.current.playbackRate = playbackRate;
        audioRef.current.play();
      }
      showToast({ type: "success", title: "Playing audio" });
    } catch (e: any) {
      showToast({ type: "error", title: "TTS failed", message: e.message });
    } finally { setTtsLoading(false); }
  };

  if (loading) {
    return (
      <AppShell>
        <div className="flex items-center justify-center py-32">
          <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
        </div>
      </AppShell>
    );
  }

  if (!incident) {
    return (
      <AppShell>
        <div className="card text-center py-16">
          <AlertTriangle className="w-12 h-12 mx-auto mb-3 text-slate-300" />
          <p className="text-lg text-hospital-muted">Incident not found</p>
          <button onClick={() => router.push("/incidents")} className="btn-secondary mt-4">Back to Incidents</button>
        </div>
      </AppShell>
    );
  }

  const sb = statusBadge(incident.status);
  const latestPlan = plans?.[0];

  return (
    <AppShell
      incidentId={id}
      cameraId={incident.camera_id}
      currentPlan={latestPlan}
      reasons={summary?.reasons || incident.reasons_current}
      onTranslate={handleTranslate}
      onReadAloud={handleTTS}
      onAcknowledge={handleAck}
      onFalseAlarm={handleFalseAlarm}
    >
      {/* Header */}
      <div className={cn("card-compact mb-6 border-2", severityBg(incident.severity_current))}>
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <div className={cn("w-16 h-16 rounded-2xl flex items-center justify-center text-white font-bold text-2xl", severityColor(incident.severity_current))}>
              {incident.severity_current}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-slate-900">{incident.verdict || "Incident"}</h2>
                <span className={cn("badge", sb.bg)}>{sb.text}</span>
              </div>
              <div className="flex items-center gap-4 mt-1 text-sm text-hospital-muted">
                <span className="flex items-center gap-1"><Clock className="w-4 h-4" />{formatSeconds(incident.time_down_s)}</span>
                <span className="flex items-center gap-1"><Shield className="w-4 h-4" />Confidence: {(incident.confidence * 100).toFixed(0)}%</span>
                <span className="flex items-center gap-1"><Activity className="w-4 h-4" />Escalation: {incident.escalation_stage}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {incident.severity_current >= 3 && !incident.acknowledged && (
              <div className="relative">
                <div className={cn("w-4 h-4 rounded-full absolute", severityColor(incident.severity_current), "pulse-ring")} />
                <div className={cn("w-4 h-4 rounded-full relative", severityColor(incident.severity_current))} />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <button
          onClick={handleAck}
          disabled={incident.acknowledged || actionLoading === "ack"}
          className="btn-success py-4 text-base flex items-center justify-center gap-2 rounded-2xl"
        >
          {actionLoading === "ack" ? <Loader2 className="w-5 h-5 animate-spin" /> : <CheckCircle className="w-5 h-5" />}
          Acknowledge
        </button>
        <button
          onClick={handleFalseAlarm}
          disabled={actionLoading === "false"}
          className="btn-secondary py-4 text-base flex items-center justify-center gap-2 rounded-2xl"
        >
          {actionLoading === "false" ? <Loader2 className="w-5 h-5 animate-spin" /> : <XCircle className="w-5 h-5" />}
          False Alarm
        </button>
        <button className="btn-secondary py-4 text-base flex items-center justify-center gap-2 rounded-2xl">
          <Phone className="w-5 h-5" />
          Call Person
        </button>
        <button className="btn-danger py-4 text-base flex items-center justify-center gap-2 rounded-2xl">
          <ArrowUpRight className="w-5 h-5" />
          Escalate
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Evidence Frames */}
        <div className="card">
          <h3 className="text-sm font-semibold text-slate-900 mb-3">Evidence Frames</h3>
          {frames.length > 0 ? (
            <div className="grid grid-cols-2 gap-2">
              {frames.slice(0, 4).map((f, i) => (
                <div key={i} className="aspect-video bg-slate-100 rounded-xl overflow-hidden">
                  <img src={`data:image/jpeg;base64,${f}`} alt={`Frame ${i + 1}`} className="w-full h-full object-cover" />
                </div>
              ))}
            </div>
          ) : (
            <div className="aspect-video bg-slate-100 rounded-xl flex items-center justify-center">
              <div className="text-center text-hospital-muted">
                <ImageIcon className="w-10 h-10 mx-auto mb-2 text-slate-300" />
                <p className="text-sm">No frames available</p>
              </div>
            </div>
          )}
        </div>

        {/* Summary & Accessibility */}
        <div className="space-y-4">
          <div className="card">
            <h3 className="text-sm font-semibold text-slate-900 mb-3">Summary</h3>
            <p className={cn("text-sm leading-relaxed", translatedText ? "text-blue-800" : "text-slate-700")}>
              {translatedText || summary?.summary_text || incident.summary_text || "Generating summary..."}
            </p>
            {translatedLang && (
              <span className="badge bg-blue-100 text-blue-700 mt-2">Translated: {translatedLang}</span>
            )}
          </div>

          {/* Translate & TTS */}
          <div className="card">
            <h3 className="text-sm font-semibold text-slate-900 mb-3">Accessibility</h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-hospital-muted block mb-1">Translate to</label>
                <div className="flex flex-wrap gap-2">
                  {LANGUAGES.map((l) => (
                    <button
                      key={l.code}
                      onClick={() => handleTranslate(l.code)}
                      disabled={translating}
                      className={cn(
                        "px-3 py-1.5 text-xs rounded-lg border transition-colors",
                        translatedLang === l.code
                          ? "bg-brand-50 border-brand-200 text-brand-700"
                          : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                      )}
                    >
                      {translating && translatedLang === l.code ? <Loader2 className="w-3 h-3 animate-spin inline" /> : null}
                      {l.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={handleTTS}
                  disabled={ttsLoading}
                  className="btn-secondary flex items-center gap-2"
                >
                  {ttsLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Volume2 className="w-4 h-4" />}
                  Read Aloud
                </button>
                <div className="flex items-center gap-1">
                  {[1, 1.25, 1.5].map((rate) => (
                    <button
                      key={rate}
                      onClick={() => {
                        setPlaybackRate(rate);
                        if (audioRef.current) audioRef.current.playbackRate = rate;
                      }}
                      className={cn(
                        "px-2 py-1 text-xs rounded-lg border",
                        playbackRate === rate ? "bg-brand-50 border-brand-200 text-brand-700" : "border-slate-200"
                      )}
                    >
                      {rate}x
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => audioRef.current?.pause()}
                  className="p-2 rounded-lg border border-slate-200 hover:bg-slate-50"
                >
                  <Pause className="w-4 h-4" />
                </button>
              </div>
              <audio ref={audioRef} className="hidden" />
            </div>
          </div>
        </div>

        {/* Reasons */}
        <div className="card">
          <h3 className="text-sm font-semibold text-slate-900 mb-3">Reasons</h3>
          <div className="space-y-2">
            {(summary?.reasons || incident.reasons_current || []).map((r: string, i: number) => (
              <div key={i} className="flex items-start gap-2">
                <div className={cn("w-1.5 h-1.5 rounded-full mt-2 flex-shrink-0", severityColor(incident.severity_current))} />
                <p className="text-sm text-slate-700">{r}</p>
              </div>
            ))}
            {(!summary?.reasons?.length && !incident.reasons_current?.length) && (
              <p className="text-sm text-hospital-muted">No reasons available yet</p>
            )}
          </div>
        </div>

        {/* Plan Steps */}
        <div className="card">
          <h3 className="text-sm font-semibold text-slate-900 mb-3">
            Current Plan {latestPlan && <span className="text-xs text-hospital-muted font-normal ml-2">v{latestPlan.version} ({latestPlan.model_used})</span>}
          </h3>
          <div className="space-y-2">
            {(latestPlan?.actions || summary?.plan_steps || []).map((step: any, i: number) => (
              <div key={i} className="flex items-center gap-3 py-2 px-3 bg-slate-50 rounded-lg">
                <div className="w-6 h-6 rounded-full bg-brand-100 text-brand-600 flex items-center justify-center text-xs font-bold">
                  {i + 1}
                </div>
                <span className="text-sm text-slate-700">{step.type || step.action_type || JSON.stringify(step)}</span>
                {step.delay_s > 0 && <span className="text-xs text-hospital-muted ml-auto">+{step.delay_s}s</span>}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div className="card mt-6">
        <h3 className="text-sm font-semibold text-slate-900 mb-3">Timeline</h3>
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {timeline.map((ev) => (
            <div key={ev.id} className="flex items-center gap-3 text-xs py-1.5 border-b border-slate-50 last:border-0">
              <span className="text-hospital-muted w-16 flex-shrink-0">
                {ev.ts ? new Date(ev.ts).toLocaleTimeString() : ""}
              </span>
              <span className="badge bg-slate-100 text-slate-600">{ev.kind}</span>
              <span className="text-slate-500 truncate flex-1">
                {ev.payload ? JSON.stringify(ev.payload).slice(0, 80) : ""}
              </span>
            </div>
          ))}
          {timeline.length === 0 && <p className="text-sm text-hospital-muted">No timeline events yet</p>}
        </div>
      </div>

      {/* Sticky mobile action bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-hospital-border p-3 flex gap-2 lg:hidden z-40">
        <button onClick={handleAck} disabled={incident.acknowledged} className="btn-success flex-1 py-3">
          <CheckCircle className="w-4 h-4 inline mr-1" /> Ack
        </button>
        <button className="btn-secondary flex-1 py-3">
          <Phone className="w-4 h-4 inline mr-1" /> Call
        </button>
        <button className="btn-danger flex-1 py-3">
          <ArrowUpRight className="w-4 h-4 inline mr-1" /> Escalate
        </button>
        <button onClick={handleFalseAlarm} className="btn-secondary flex-1 py-3">
          <XCircle className="w-4 h-4 inline mr-1" /> False
        </button>
      </div>
    </AppShell>
  );
}
