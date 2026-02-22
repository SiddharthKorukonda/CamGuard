"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import { Camera, Plus, ChevronRight, Loader2, Wifi, WifiOff, Video, Upload } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { showToast } from "@/components/Toast";

export default function CamerasPage() {
  const router = useRouter();
  const videoInputRef = useRef<HTMLInputElement>(null);
  const [cameras, setCameras] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showRegister, setShowRegister] = useState(false);
  const [registering, setRegistering] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [form, setForm] = useState({
    name: "",
    room_type: "bedroom",
  });

  const fetchCameras = async () => {
    try {
      const data = await api.listCameras();
      setCameras(data);
    } catch {} finally { setLoading(false); }
  };

  useEffect(() => { fetchCameras(); }, []);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegistering(true);
    try {
      const cam = await api.registerCamera(form);
      showToast({ type: "success", title: "Camera registered" });
      try {
        await api.startCameraDetection(cam.id, 0);
        showToast({ type: "success", title: "Detection started" });
      } catch (err: any) {
        showToast({ type: "warning", title: "Camera registered but detection not started", message: err.message });
      }
      setShowRegister(false);
      setForm({ name: "", room_type: "bedroom" });
      fetchCameras();
    } catch (err: any) {
      showToast({ type: "error", title: "Registration failed", message: err.message });
    } finally {
      setRegistering(false);
    }
  };

  const handleQuickUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const result = await api.quickUploadVideo(file, "bedroom");
      showToast({ type: "success", title: "Video uploaded & detection started" });
      fetchCameras();
      router.push(`/cameras/${result.camera_id}`);
    } catch (err: any) {
      showToast({ type: "error", title: "Upload failed", message: err.message });
    } finally {
      setUploading(false);
      if (videoInputRef.current) videoInputRef.current.value = "";
    }
  };

  return (
    <AppShell>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Cameras</h2>
          <p className="text-sm text-hospital-muted">{cameras.length} camera(s) registered</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => videoInputRef.current?.click()}
            disabled={uploading}
            className="btn-secondary flex items-center gap-2"
          >
            {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            Upload Video
          </button>
          <input
            ref={videoInputRef}
            type="file"
            accept="video/*,.mov,.mp4,.avi,.mkv"
            onChange={handleQuickUpload}
            className="hidden"
          />
          <button onClick={() => setShowRegister(!showRegister)} className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Add New Camera
          </button>
        </div>
      </div>

      {showRegister && (
        <form onSubmit={handleRegister} className="card mb-6 space-y-4">
          <h3 className="text-sm font-semibold">Add New Camera</h3>
          <p className="text-xs text-hospital-muted">Emergency contacts from your onboarding setup will be used automatically</p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-hospital-muted block mb-1">Camera Name</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input-field" placeholder="Bedroom Camera" required />
            </div>
            <div>
              <label className="text-xs text-hospital-muted block mb-1">Room Type</label>
              <select value={form.room_type} onChange={(e) => setForm({ ...form, room_type: e.target.value })} className="input-field">
                <option value="bedroom">Bedroom</option>
                <option value="nursery">Nursery</option>
                <option value="bathroom">Bathroom</option>
                <option value="living_room">Living Room</option>
                <option value="hallway">Hallway</option>
              </select>
            </div>
          </div>
          <div className="flex gap-3">
            <button type="submit" disabled={registering} className="btn-primary flex items-center gap-2">
              {registering ? <Loader2 className="w-4 h-4 animate-spin" /> : <Camera className="w-4 h-4" />}
              Add Camera & Start Detection
            </button>
            <button type="button" onClick={() => setShowRegister(false)} className="btn-secondary">Cancel</button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="card flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
        </div>
      ) : cameras.length === 0 ? (
        <div className="card text-center py-16 text-hospital-muted">
          <Camera className="w-12 h-12 mx-auto mb-3 text-slate-300" />
          <p className="text-lg">No cameras registered</p>
          <p className="text-sm mt-2">Click &quot;Add New Camera&quot; to get started</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {cameras.map((cam) => (
            <Link key={cam.id} href={`/cameras/${cam.id}`}>
              <div className="card-compact hover:shadow-md transition-shadow cursor-pointer">
                <div className="flex items-center gap-4">
                  <div className={cn("w-12 h-12 rounded-xl flex items-center justify-center", cam.status === "online" ? "bg-green-50" : "bg-slate-100")}>
                    {cam.status === "online" ? <Wifi className="w-6 h-6 text-green-600" /> : <WifiOff className="w-6 h-6 text-slate-400" />}
                  </div>
                  <div className="flex-1">
                    <h4 className="font-medium text-sm">{cam.name}</h4>
                    <p className="text-xs text-hospital-muted">{cam.room_type} • Risk: {(cam.risk_score * 100).toFixed(0)}%</p>
                  </div>
                  <ChevronRight className="w-5 h-5 text-slate-400" />
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </AppShell>
  );
}
