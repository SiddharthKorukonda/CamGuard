"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import { Camera, Save, Loader2, Settings, Video, Play, Square, Upload } from "lucide-react";
import { api } from "@/lib/api";
import { showToast } from "@/components/Toast";

export default function CameraDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [camera, setCamera] = useState<any>(null);
  const [config, setConfig] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [starting, setStarting] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [cam, cfg, active] = await Promise.all([
          api.getCamera(id),
          api.getCameraConfig(id).catch(() => null),
          api.getActiveVisionCameras().catch(() => ({ cameras: [] })),
        ]);
        setCamera(cam);
        setConfig(cfg?.config || {});
        setStreaming(active.cameras?.includes(id) || false);
      } catch {} finally { setLoading(false); }
    };
    load();
  }, [id]);

  const handleStart = async () => {
    setStarting(true);
    try {
      await api.startCameraDetection(id, 0);
      setStreaming(true);
      showToast({ type: "success", title: "Detection started" });
    } catch (e: any) {
      const msg = e.message || "";
      if (msg.includes("camera device") || msg.includes("Could not open")) {
        showToast({
          type: "error",
          title: "Camera not available",
          message: "Camera access is not available in Docker on macOS. Please use 'Add Video' to upload a video file instead.",
        });
      } else {
        showToast({ type: "error", title: "Failed to start", message: msg });
      }
    } finally { setStarting(false); }
  };

  const handleStop = async () => {
    try {
      await api.stopCameraDetection(id);
      setStreaming(false);
      showToast({ type: "success", title: "Detection stopped" });
    } catch {}
  };

  const handleVideoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await api.uploadVideo(id, file);
      setStreaming(true);
      showToast({ type: "success", title: "Video uploaded and detection started" });
    } catch (err: any) {
      showToast({ type: "error", title: "Upload failed", message: err.message });
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.updateCamera(id, {
        room_type: camera?.room_type,
        config: config,
      });
      showToast({ type: "success", title: "Camera settings saved" });
    } catch (e: any) {
      showToast({ type: "error", title: "Save failed", message: e.message });
    } finally { setSaving(false); }
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

  return (
    <AppShell cameraId={id}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">{camera?.name || "Camera"}</h2>
          <p className="text-sm text-hospital-muted">{camera?.room_type} • ID: {id?.slice(0, 12)}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowConfig(!showConfig)} className="btn-secondary flex items-center gap-2 text-sm">
            <Settings className="w-4 h-4" />
            {showConfig ? "Hide Config" : "Config"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            onChange={handleVideoUpload}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="btn-secondary flex items-center gap-2 text-sm"
          >
            {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            Add Video
          </button>
          {!streaming ? (
            <button onClick={handleStart} disabled={starting} className="btn-primary flex items-center gap-2 text-sm">
              {starting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              Start Detection
            </button>
          ) : (
            <button onClick={handleStop} className="btn-danger flex items-center gap-2 text-sm">
              <Square className="w-4 h-4" />
              Stop Detection
            </button>
          )}
        </div>
      </div>

      {/* Live Feed - Full width */}
      <div className="mb-6">
        {streaming ? (
          <div className="relative w-full rounded-xl overflow-hidden bg-black" style={{ aspectRatio: "16/9" }}>
            <img
              src={api.cameraStreamUrl(id)}
              alt="Live camera feed"
              className="w-full h-full object-contain"
            />
            <div className="absolute top-3 left-3 flex items-center gap-2 bg-black/60 px-3 py-1.5 rounded-lg">
              <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
              <span className="text-white text-xs font-medium">LIVE</span>
            </div>
          </div>
        ) : (
          <div className="w-full rounded-xl bg-slate-100 flex flex-col items-center justify-center py-32 border border-hospital-border">
            <Camera className="w-16 h-16 text-slate-300 mb-4" />
            <p className="text-hospital-muted">Camera is not streaming</p>
            <p className="text-xs text-slate-400 mt-1">Click &quot;Start Detection&quot; or &quot;Add Video&quot; to begin</p>
          </div>
        )}
      </div>

      {/* Config Section (toggled) */}
      {showConfig && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card">
            <h3 className="text-sm font-semibold text-slate-900 mb-3 flex items-center gap-2">
              <Settings className="w-4 h-4" /> Configuration
            </h3>
            <div className="space-y-3">
              {config && Object.entries(config).map(([key, val]) => (
                <div key={key} className="flex items-center justify-between">
                  <label className="text-xs text-hospital-muted capitalize">{key.replace(/_/g, " ")}</label>
                  <input
                    type="number"
                    step="0.1"
                    value={val as number}
                    onChange={(e) => setConfig({ ...config, [key]: parseFloat(e.target.value) || 0 })}
                    className="input-field w-24 text-right text-sm"
                  />
                </div>
              ))}
            </div>
            <button onClick={handleSave} disabled={saving} className="btn-primary mt-4 flex items-center gap-2">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Save
            </button>
          </div>

          <div className="card">
            <h3 className="text-sm font-semibold text-slate-900 mb-3">Camera Info</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-hospital-muted">Status</span><span>{camera?.status}</span></div>
              <div className="flex justify-between"><span className="text-hospital-muted">Risk Score</span><span>{((camera?.risk_score || 0) * 100).toFixed(0)}%</span></div>
              <div className="flex justify-between"><span className="text-hospital-muted">Primary Contact</span><span>{camera?.primary_contact || "Not set"}</span></div>
              <div className="flex justify-between"><span className="text-hospital-muted">Backup Contact</span><span>{camera?.backup_contact || "Not set"}</span></div>
              <div className="flex justify-between"><span className="text-hospital-muted">Voice Enabled</span><span>{camera?.voice_enabled ? "Yes" : "No"}</span></div>
              <div className="flex justify-between"><span className="text-hospital-muted">SMS Enabled</span><span>{camera?.sms_enabled ? "Yes" : "No"}</span></div>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
