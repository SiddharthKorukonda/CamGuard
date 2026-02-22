import React, { useState, useRef } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from "react-native";
import { api } from "../lib/api";

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp: Date;
}

export default function ChatBotScreen() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      text: "Hello! I'm CamGuard AI, your intelligent monitoring assistant. I can help you understand camera feeds, manage incidents, configure alerts, and answer questions about the caregiver monitoring system.\n\nHow can I help you today?",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const flatListRef = useRef<FlatList>(null);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setInput("");

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      text,
      timestamp: new Date(),
    };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setLoading(true);

    try {
      const history = newMessages.map((m) => ({ role: m.role, text: m.text }));
      const res = await api.sendChatMessage({
        message: text,
        session_id: sessionId || undefined,
        history,
      });
      if (res.session_id) setSessionId(res.session_id);

      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          text: res.response || "I'm here to help. Please try again.",
          timestamp: new Date(),
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          text: "I'm having trouble connecting to the AI backend right now. The monitoring system is still running and will alert you to any incidents. Please try again in a moment.",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => flatListRef.current?.scrollToEnd({ animated: true }), 100);
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>AI Assistant</Text>
        <View style={styles.statusRow}>
          <View style={styles.onlineDot} />
          <Text style={styles.subtitle}>Always monitoring</Text>
        </View>
      </View>

      <KeyboardAvoidingView
        style={styles.chatArea}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        keyboardVerticalOffset={90}
      >
        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.messageList}
          onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
          renderItem={({ item }) => (
            <View
              style={[
                styles.messageBubble,
                item.role === "user" ? styles.userBubble : styles.assistantBubble,
              ]}
            >
              {item.role === "assistant" && (
                <Text style={styles.botLabel}>CamGuard AI</Text>
              )}
              <Text
                style={[
                  styles.messageText,
                  item.role === "user" ? styles.userText : styles.assistantText,
                ]}
              >
                {item.text}
              </Text>
              <Text
                style={[
                  styles.timeStamp,
                  { color: item.role === "user" ? "rgba(255,255,255,0.6)" : "#94A3B8" },
                ]}
              >
                {formatTime(item.timestamp)}
              </Text>
            </View>
          )}
        />

        {loading && (
          <View style={styles.typingRow}>
            <ActivityIndicator size="small" color="#4F46E5" />
            <Text style={styles.typingText}>Thinking...</Text>
          </View>
        )}

        <View style={styles.inputRow}>
          <TextInput
            style={styles.input}
            value={input}
            onChangeText={setInput}
            placeholder="Ask about monitoring, incidents..."
            placeholderTextColor="#94A3B8"
            multiline
            maxLength={1000}
            onSubmitEditing={sendMessage}
            returnKeyType="send"
          />
          <TouchableOpacity
            style={[styles.sendBtn, (!input.trim() || loading) && styles.sendBtnDisabled]}
            onPress={sendMessage}
            disabled={!input.trim() || loading}
          >
            <Text style={styles.sendBtnText}>↑</Text>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F8FAFC" },
  header: { paddingHorizontal: 20, paddingTop: 60, paddingBottom: 16, backgroundColor: "#4F46E5" },
  title: { fontSize: 28, fontWeight: "800", color: "#FFFFFF" },
  statusRow: { flexDirection: "row", alignItems: "center", marginTop: 4, gap: 6 },
  onlineDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: "#34D399" },
  subtitle: { fontSize: 14, color: "#C7D2FE" },
  chatArea: { flex: 1 },
  messageList: { paddingHorizontal: 16, paddingVertical: 12 },
  messageBubble: {
    maxWidth: "85%",
    borderRadius: 18,
    padding: 14,
    marginBottom: 10,
  },
  userBubble: {
    alignSelf: "flex-end",
    backgroundColor: "#4F46E5",
    borderBottomRightRadius: 4,
  },
  assistantBubble: {
    alignSelf: "flex-start",
    backgroundColor: "#FFFFFF",
    borderBottomLeftRadius: 4,
    shadowColor: "#000",
    shadowOpacity: 0.04,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 1,
  },
  botLabel: { fontSize: 11, fontWeight: "700", color: "#4F46E5", marginBottom: 4 },
  messageText: { fontSize: 15, lineHeight: 22 },
  userText: { color: "#FFFFFF" },
  assistantText: { color: "#334155" },
  timeStamp: { fontSize: 10, marginTop: 6, textAlign: "right" },
  typingRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 20,
    paddingVertical: 8,
    gap: 8,
  },
  typingText: { fontSize: 13, color: "#64748B" },
  inputRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: "#FFFFFF",
    borderTopWidth: 1,
    borderTopColor: "#E2E8F0",
    gap: 8,
  },
  input: {
    flex: 1,
    backgroundColor: "#F1F5F9",
    borderRadius: 22,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: 15,
    maxHeight: 100,
    color: "#1E293B",
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#4F46E5",
    justifyContent: "center",
    alignItems: "center",
  },
  sendBtnDisabled: { backgroundColor: "#CBD5E1" },
  sendBtnText: { color: "#FFFFFF", fontSize: 20, fontWeight: "700" },
});
