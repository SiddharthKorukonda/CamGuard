const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

async function requestRaw(path: string, options?: RequestInit): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
}

export const api = {
  health: () => request<any>("/health"),

  // Cameras
  listCameras: () => request<any[]>("/api/cameras"),
  getCamera: (id: string) => request<any>(`/api/cameras/${id}`),
  registerCamera: (data: any) => request<any>("/api/cameras/register", { method: "POST", body: JSON.stringify(data) }),
  updateCamera: (id: string, data: any) => request<any>(`/api/cameras/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  getCameraConfig: (id: string) => request<any>(`/api/cameras/${id}/config`),

  // Incidents
  listIncidents: (params?: { status?: string; severity_min?: number }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.severity_min) qs.set("severity_min", String(params.severity_min));
    const q = qs.toString();
    return request<any[]>(`/api/incidents${q ? `?${q}` : ""}`);
  },
  getIncident: (id: string) => request<any>(`/api/incidents/${id}`),
  getIncidentTimeline: (id: string) => request<any[]>(`/api/incidents/${id}/timeline`),
  getIncidentPlan: (id: string) => request<any[]>(`/api/incidents/${id}/plan`),
  getIncidentFrames: (id: string) => request<any>(`/api/incidents/${id}/frames`),
  getIncidentSummary: (id: string) => request<any>(`/api/incidents/${id}/summary`),
  ackIncident: (id: string, ackBy?: string) =>
    request<any>(`/api/incidents/${id}/ack`, { method: "POST", body: JSON.stringify({ ack_by: ackBy || "caregiver" }) }),
  falseAlarm: (id: string) => request<any>(`/api/incidents/${id}/false_alarm`, { method: "POST" }),
  translateIncident: (id: string, lang: string, text?: string) =>
    request<any>(`/api/incidents/${id}/translate`, { method: "POST", body: JSON.stringify({ target_language: lang, text }) }),
  ttsIncident: async (id: string, text?: string): Promise<Blob> => {
    const res = await requestRaw(`/api/incidents/${id}/tts`, {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error(`TTS failed: ${res.status}`);
    return res.blob();
  },

  // Agent
  sendAgentInstruction: (data: { camera_id?: string; text: string; priority?: string; duration_minutes?: number }) =>
    request<any>("/api/agent/monitoring-instructions", { method: "POST", body: JSON.stringify(data) }),

  // Demo
  demoPrevention: () => request<any>("/api/demo/prevention", { method: "POST" }),
  demoFall: () => request<any>("/api/demo/fall", { method: "POST" }),

  // Vision / Camera
  startCameraDetection: (cameraId: string, device: number = 0) =>
    request<any>(`/api/vision/start/${cameraId}?device=${device}`, { method: "POST" }),
  stopCameraDetection: (cameraId: string) =>
    request<any>(`/api/vision/stop/${cameraId}`, { method: "POST" }),
  cameraStreamUrl: (cameraId: string) => `${API_BASE}/api/vision/stream/${cameraId}`,
  uploadVideo: async (cameraId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE}/api/vision/upload-video/${cameraId}`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    return res.json();
  },
  getActiveVisionCameras: () => request<any>("/api/vision/active"),

  // Onboarding
  saveOnboarding: (data: { monitoring_type: string; primary_contact: string; backup_contact: string }) =>
    request<any>("/api/vision/onboarding", { method: "POST", body: JSON.stringify(data) }),
  getOnboarding: () => request<any>("/api/vision/onboarding").catch(() => null),

  // Translate
  translateText: (text: string, targetLang: string) =>
    request<any>("/api/incidents/translate-text", {
      method: "POST",
      body: JSON.stringify({ text, target_language: targetLang }),
    }).catch(() => ({ translated_text: text })),

  translateBatch: (texts: string[], targetLang: string) =>
    request<{ translations: string[]; language: string }>("/api/incidents/translate-batch", {
      method: "POST",
      body: JSON.stringify({ texts, target_language: targetLang }),
    }).catch(() => ({ translations: texts, language: targetLang })),

  // Chat
  sendChatMessage: (data: { message: string; session_id?: string; camera_id?: string; history?: any[] }) =>
    request<{ response: string; session_id: string }>("/api/agent/chat", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Performance
  getPerformance: () => request<any>("/api/agent/performance"),

  // Quick video upload (auto-creates camera)
  quickUploadVideo: async (file: File, roomType: string = "bedroom") => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("room_type", roomType);
    const res = await fetch(`${API_BASE}/api/vision/quick-upload`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    return res.json();
  },
};
