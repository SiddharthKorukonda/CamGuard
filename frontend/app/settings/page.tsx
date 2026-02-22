"use client";

import { useState } from "react";
import AppShell from "@/components/AppShell";
import {
  User, Phone, Globe, Shield, Bell, Eye,
  Save, Loader2, Play, ZapOff,
} from "lucide-react";
import { api } from "@/lib/api";
import { LANGUAGES } from "@/lib/utils";
import { showToast } from "@/components/Toast";
import { getUser } from "@/lib/auth";

export default function SettingsPage() {
  const user = getUser();
  const [language, setLanguage] = useState("en");
  const [sensitivity, setSensitivity] = useState("medium");
  const [retention, setRetention] = useState(30);
  const [escalationTiming, setEscalationTiming] = useState(60);
  const [largeText, setLargeText] = useState(false);
  const [highContrast, setHighContrast] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const [saving, setSaving] = useState(false);
  const [demoLoading, setDemoLoading] = useState("");

  const handleSave = () => {
    setSaving(true);
    setTimeout(() => {
      setSaving(false);
      showToast({ type: "success", title: "Settings saved" });
    }, 500);
  };

  const toggleDark = () => {
    const next = !darkMode;
    setDarkMode(next);
    if (next) document.documentElement.classList.add("dark");
    else document.documentElement.classList.remove("dark");
  };

  const runDemo = async (type: "prevention" | "fall") => {
    setDemoLoading(type);
    try {
      if (type === "prevention") await api.demoPrevention();
      else await api.demoFall();
      showToast({ type: "success", title: `${type} demo triggered!` });
    } catch (e: any) {
      showToast({ type: "error", title: "Demo failed", message: e.message });
    } finally { setDemoLoading(""); }
  };

  return (
    <AppShell>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Settings</h2>
          <p className="text-sm text-hospital-muted">Configure your profile and preferences</p>
        </div>
        <button onClick={handleSave} disabled={saving} className="btn-primary flex items-center gap-2">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Save All
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Profile */}
        <div className="card space-y-4">
          <h3 className="text-sm font-semibold flex items-center gap-2"><User className="w-4 h-4" /> Profile</h3>
          <div>
            <label className="text-xs text-hospital-muted block mb-1">Name</label>
            <input className="input-field" value={user?.name || ""} readOnly />
          </div>
          <div>
            <label className="text-xs text-hospital-muted block mb-1">Email</label>
            <input className="input-field" value={user?.email || ""} readOnly />
          </div>
        </div>

        {/* Contacts */}
        <div className="card space-y-4">
          <h3 className="text-sm font-semibold flex items-center gap-2"><Phone className="w-4 h-4" /> Contacts</h3>
          <div>
            <label className="text-xs text-hospital-muted block mb-1">Primary Contact Phone</label>
            <input className="input-field" placeholder="+1234567890" />
          </div>
          <div>
            <label className="text-xs text-hospital-muted block mb-1">Backup Contact Phone</label>
            <input className="input-field" placeholder="+1234567890" />
          </div>
        </div>

        {/* Language & Accessibility */}
        <div className="card space-y-4">
          <h3 className="text-sm font-semibold flex items-center gap-2"><Globe className="w-4 h-4" /> Language & Accessibility</h3>
          <div>
            <label className="text-xs text-hospital-muted block mb-1">Default Language</label>
            <select value={language} onChange={(e) => setLanguage(e.target.value)} className="input-field">
              {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
            </select>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm">Large Text Mode</span>
            <button
              onClick={() => setLargeText(!largeText)}
              className={`w-12 h-6 rounded-full transition-colors ${largeText ? "bg-brand-600" : "bg-slate-300"}`}
            >
              <div className={`w-5 h-5 rounded-full bg-white shadow-sm transform transition-transform ${largeText ? "translate-x-6" : "translate-x-0.5"}`} />
            </button>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm">High Contrast</span>
            <button
              onClick={() => setHighContrast(!highContrast)}
              className={`w-12 h-6 rounded-full transition-colors ${highContrast ? "bg-brand-600" : "bg-slate-300"}`}
            >
              <div className={`w-5 h-5 rounded-full bg-white shadow-sm transform transition-transform ${highContrast ? "translate-x-6" : "translate-x-0.5"}`} />
            </button>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm">Night Mode</span>
            <button
              onClick={toggleDark}
              className={`w-12 h-6 rounded-full transition-colors ${darkMode ? "bg-brand-600" : "bg-slate-300"}`}
            >
              <div className={`w-5 h-5 rounded-full bg-white shadow-sm transform transition-transform ${darkMode ? "translate-x-6" : "translate-x-0.5"}`} />
            </button>
          </div>
        </div>

        {/* Escalation & Sensitivity */}
        <div className="card space-y-4">
          <h3 className="text-sm font-semibold flex items-center gap-2"><Shield className="w-4 h-4" /> Escalation Policy</h3>
          <div>
            <label className="text-xs text-hospital-muted block mb-1">Sensitivity</label>
            <select value={sensitivity} onChange={(e) => setSensitivity(e.target.value)} className="input-field">
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-hospital-muted block mb-1">Privacy Retention (days)</label>
            <input type="number" value={retention} onChange={(e) => setRetention(Number(e.target.value))} className="input-field" />
          </div>
          <div>
            <label className="text-xs text-hospital-muted block mb-1">Escalation Timing (seconds)</label>
            <input type="number" value={escalationTiming} onChange={(e) => setEscalationTiming(Number(e.target.value))} className="input-field" />
          </div>
        </div>

        {/* Rehearsal / Demo Mode */}
        <div className="card space-y-4 lg:col-span-2">
          <h3 className="text-sm font-semibold flex items-center gap-2"><Play className="w-4 h-4" /> Rehearsal Mode</h3>
          <p className="text-xs text-hospital-muted">Test the system with simulated scenarios</p>
          <div className="flex gap-4">
            <button
              onClick={() => runDemo("prevention")}
              disabled={!!demoLoading}
              className="btn-secondary flex items-center gap-2"
            >
              {demoLoading === "prevention" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
              Run Prevention Demo
            </button>
            <button
              onClick={() => runDemo("fall")}
              disabled={!!demoLoading}
              className="btn-danger flex items-center gap-2"
            >
              {demoLoading === "fall" ? <Loader2 className="w-4 h-4 animate-spin" /> : <ZapOff className="w-4 h-4" />}
              Run Fall Demo
            </button>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
