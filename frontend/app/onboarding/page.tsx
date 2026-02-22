"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Shield, Baby, UserRound, Users, Phone, ChevronRight } from "lucide-react";
import { setOnboarded } from "@/lib/auth";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const monitoringTypes = [
  { id: "old_people", label: "Elderly Person", icon: UserRound, desc: "Monitor an elderly person for fall prevention" },
  { id: "babies", label: "Baby / Infant", icon: Baby, desc: "Monitor a baby in a crib for safety" },
  { id: "others", label: "Others", icon: Users, desc: "General monitoring and fall detection" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [monitoringType, setMonitoringType] = useState("");
  const [primaryPhone, setPrimaryPhone] = useState("");
  const [backupPhone, setBackupPhone] = useState("");
  const [saving, setSaving] = useState(false);

  const handleNext = async () => {
    if (!monitoringType) return;
    setSaving(true);
    try {
      await api.saveOnboarding({
        monitoring_type: monitoringType,
        primary_contact: primaryPhone,
        backup_contact: backupPhone,
      });
    } catch {}
    setOnboarded();
    setSaving(false);
    router.push("/");
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-red-50/30 to-slate-50">
      <div className="w-full max-w-lg">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-brand-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-brand-200">
            <Shield className="w-9 h-9 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-slate-900">Welcome to CamGuard</h1>
          <p className="text-hospital-muted mt-2">Let&apos;s set up your monitoring profile</p>
        </div>

        <div className="card space-y-6">
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">Who are you monitoring?</h3>
            <div className="space-y-3">
              {monitoringTypes.map((type) => (
                <button
                  key={type.id}
                  onClick={() => setMonitoringType(type.id)}
                  className={cn(
                    "w-full flex items-center gap-4 p-4 rounded-xl border-2 transition-all text-left",
                    monitoringType === type.id
                      ? "border-brand-600 bg-brand-50"
                      : "border-slate-200 hover:border-slate-300 bg-white"
                  )}
                >
                  <div className={cn(
                    "w-12 h-12 rounded-xl flex items-center justify-center",
                    monitoringType === type.id ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-500"
                  )}>
                    <type.icon className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="font-medium text-sm">{type.label}</p>
                    <p className="text-xs text-hospital-muted">{type.desc}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-slate-700">Emergency Contacts</h3>
            <div>
              <label className="text-xs text-hospital-muted block mb-1">Primary Phone Number</label>
              <div className="relative">
                <Phone className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  value={primaryPhone}
                  onChange={(e) => setPrimaryPhone(e.target.value)}
                  placeholder="+1 917-770-6048"
                  className="input-field pl-10"
                />
              </div>
            </div>
            <div>
              <label className="text-xs text-hospital-muted block mb-1">Secondary Phone Number</label>
              <div className="relative">
                <Phone className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  value={backupPhone}
                  onChange={(e) => setBackupPhone(e.target.value)}
                  placeholder="+1 234-567-8900"
                  className="input-field pl-10"
                />
              </div>
            </div>
          </div>

          <button
            onClick={handleNext}
            disabled={!monitoringType || saving}
            className="btn-primary w-full py-3 text-base flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {saving ? "Setting up..." : "Next"}
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
