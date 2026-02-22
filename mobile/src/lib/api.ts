const API_BASE = "http://localhost:8000";

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

export const api = {
  health: () => request<any>("/health"),

  listCameras: () => request<any[]>("/api/cameras"),
  getCamera: (id: string) => request<any>(`/api/cameras/${id}`),
  cameraStreamUrl: (cameraId: string) => `${API_BASE}/api/vision/stream/${cameraId}`,

  listIncidents: (params?: { status?: string }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    const q = qs.toString();
    return request<any[]>(`/api/incidents${q ? `?${q}` : ""}`);
  },
  getIncident: (id: string) => request<any>(`/api/incidents/${id}`),
  ackIncident: (id: string) =>
    request<any>(`/api/incidents/${id}/ack`, {
      method: "POST",
      body: JSON.stringify({ ack_by: "mobile_user" }),
    }),

  sendChatMessage: (data: {
    message: string;
    session_id?: string;
    history?: any[];
  }) =>
    request<{ response: string; session_id: string }>("/api/agent/chat", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

export function connectWebSocket(onMessage: (data: any) => void): () => void {
  const ws = new WebSocket(`ws://localhost:8000/ws`);
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch {}
  };
  ws.onerror = () => {};
  ws.onclose = () => {
    setTimeout(() => connectWebSocket(onMessage), 3000);
  };
  return () => ws.close();
}
