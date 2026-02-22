"use client";

type WSEventHandler = (event: any) => void;

let socket: WebSocket | null = null;
let listeners: WSEventHandler[] = [];
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

export function connectWS() {
  if (socket?.readyState === WebSocket.OPEN) return;

  const url = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";
  socket = new WebSocket(url);

  socket.onopen = () => {
    console.log("[WS] Connected");
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  socket.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      listeners.forEach((fn) => fn(data));
    } catch {}
  };

  socket.onclose = () => {
    console.log("[WS] Disconnected, reconnecting in 3s...");
    reconnectTimer = setTimeout(connectWS, 3000);
  };

  socket.onerror = () => {
    socket?.close();
  };
}

export function onWSEvent(handler: WSEventHandler) {
  listeners.push(handler);
  return () => {
    listeners = listeners.filter((fn) => fn !== handler);
  };
}

export function disconnectWS() {
  socket?.close();
  socket = null;
  listeners = [];
}
