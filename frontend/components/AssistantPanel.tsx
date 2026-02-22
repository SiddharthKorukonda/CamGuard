"use client";

import { useState, useRef } from "react";
import {
  Bot,
  Send,
  Globe,
  Volume2,
  FileText,
  Sparkles,
  CheckCircle,
  XCircle,
  Phone,
  ArrowUpRight,
  Loader2,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Message {
  role: "user" | "assistant";
  text: string;
  watchlist?: any;
}

interface Props {
  incidentId?: string;
  cameraId?: string;
  onTranslate?: (lang: string) => void;
  onReadAloud?: () => void;
  onAcknowledge?: () => void;
  onFalseAlarm?: () => void;
  onEscalate?: () => void;
  currentPlan?: any;
  reasons?: string[];
}

export default function AssistantPanel({
  incidentId,
  cameraId,
  onTranslate,
  onReadAloud,
  onAcknowledge,
  onFalseAlarm,
  onEscalate,
  currentPlan,
  reasons,
}: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>("");
  const inputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const sendMessage = async () => {
    if (!input.trim()) return;
    const text = input.trim();
    setInput("");
    const newMessages: Message[] = [...messages, { role: "user", text }];
    setMessages(newMessages);
    setLoading(true);

    try {
      const history = newMessages.map((m) => ({ role: m.role, text: m.text }));
      const res = await api.sendChatMessage({
        message: text,
        session_id: sessionId || undefined,
        camera_id: cameraId || undefined,
        history,
      });
      if (res.session_id) setSessionId(res.session_id);
      setMessages((m) => [
        ...m,
        { role: "assistant", text: res.response || "I'm here to help. Please try again." },
      ]);
    } catch {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: "I'm currently having trouble connecting to the AI backend. The CamGuard monitoring system is still active and will alert you to any incidents. Please try sending your message again in a moment.",
        },
      ]);
    } finally {
      setLoading(false);
      setTimeout(scrollToBottom, 100);
    }
  };

  const chips = [
    { label: "Translate", icon: Globe, action: () => onTranslate?.("es") },
    { label: "Read aloud", icon: Volume2, action: onReadAloud },
    { label: "Create report", icon: FileText, action: () => {} },
    { label: "Recommend", icon: Sparkles, action: () => {} },
  ];

  return (
    <div className="w-80 h-full bg-white border-l border-hospital-border flex flex-col fixed right-0 top-0 z-30">
      {/* Header */}
      <div className="p-4 border-b border-hospital-border">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-brand-50 rounded-lg flex items-center justify-center">
            <Bot className="w-5 h-5 text-brand-600" />
          </div>
          <div>
            <h3 className="font-semibold text-sm">AI Assistant</h3>
            <p className="text-xs text-hospital-muted">Always monitoring</p>
          </div>
          <div className="ml-auto w-2 h-2 bg-green-500 rounded-full" />
        </div>
      </div>

      {/* Quick chips */}
      <div className="p-3 border-b border-hospital-border">
        <div className="flex flex-wrap gap-2">
          {chips.map((chip) => (
            <button
              key={chip.label}
              onClick={chip.action}
              className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-full bg-slate-100 text-slate-600 hover:bg-brand-50 hover:text-brand-600 transition-colors"
            >
              <chip.icon className="w-3 h-3" />
              {chip.label}
            </button>
          ))}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="text-center py-8">
            <Bot className="w-10 h-10 text-slate-300 mx-auto mb-3" />
            <p className="text-sm font-medium text-slate-600">You have full control</p>
            <p className="text-xs text-slate-400 mt-2 leading-relaxed px-2">
              Tell the AI agent what to watch for and it will adapt its monitoring workflow in real-time. Your instructions shape how the system detects, alerts, and responds.
            </p>
            <p className="text-xs text-slate-400 mt-2 italic">e.g. &quot;She is dizzy tonight, watch closely&quot;</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={cn(
              "rounded-xl px-3 py-2 text-sm",
              msg.role === "user"
                ? "ml-auto bg-brand-600 text-white max-w-[85%]"
                : "bg-slate-100 text-slate-700 max-w-[95%]"
            )}
          >
            <div className="whitespace-pre-wrap break-words leading-relaxed">{msg.text}</div>
            {msg.watchlist && (
              <div className="mt-2 p-2 bg-white rounded-lg text-xs space-y-1">
                {msg.watchlist.conditions?.map((c: string, j: number) => (
                  <div key={j} className="flex items-center gap-1">
                    <Sparkles className="w-3 h-3 text-brand-500" />
                    <span>{c}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-sm text-hospital-muted">
            <Loader2 className="w-4 h-4 animate-spin" />
            Thinking...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Agent Actions */}
      {incidentId && (
        <div className="p-3 border-t border-hospital-border space-y-2">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Agent Actions</p>
          <div className="grid grid-cols-2 gap-2">
            <button onClick={onAcknowledge} className="btn-success text-xs py-2 rounded-lg">
              <CheckCircle className="w-3 h-3 inline mr-1" />
              Acknowledge
            </button>
            <button onClick={onFalseAlarm} className="btn-secondary text-xs py-2 rounded-lg">
              <XCircle className="w-3 h-3 inline mr-1" />
              False Alarm
            </button>
            <button onClick={() => {}} className="btn-secondary text-xs py-2 rounded-lg">
              <Phone className="w-3 h-3 inline mr-1" />
              Call Person
            </button>
            <button onClick={onEscalate} className="btn-danger text-xs py-2 rounded-lg">
              <ArrowUpRight className="w-3 h-3 inline mr-1" />
              Escalate
            </button>
          </div>
        </div>
      )}

      {/* Current Plan */}
      {currentPlan && (
        <div className="p-3 border-t border-hospital-border">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Current Agent Plan</p>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {(currentPlan.actions || currentPlan)?.map?.((step: any, i: number) => (
              <div key={i} className="flex items-center gap-2 text-xs text-slate-600">
                <div className="w-4 h-4 rounded-full bg-brand-100 text-brand-600 flex items-center justify-center text-[10px] font-bold">
                  {i + 1}
                </div>
                <span>{step.type || step.action_type || JSON.stringify(step)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Reasons */}
      {reasons && reasons.length > 0 && (
        <div className="p-3 border-t border-hospital-border">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Reasons</p>
          <div className="space-y-1 max-h-24 overflow-y-auto">
            {reasons.map((r, i) => (
              <p key={i} className="text-xs text-slate-600">• {r}</p>
            ))}
          </div>
        </div>
      )}

      {/* Chat Input */}
      <div className="p-3 border-t border-hospital-border">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            placeholder="Tell the AI what to watch..."
            className="input-field text-sm py-2"
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="btn-primary px-3 py-2"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
