import React, { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  Alert,
  ActivityIndicator,
} from "react-native";
import { api, connectWebSocket } from "../lib/api";

interface Incident {
  incident_id: string;
  camera_id: string;
  status: string;
  verdict: string;
  severity_current: number;
  severity_seed: number;
  time_down_s: number;
  acknowledged: boolean;
  reasons_current: string[];
  created_at: string;
  summary_text?: string;
}

const severityConfig: Record<number, { label: string; color: string; bg: string }> = {
  1: { label: "Low", color: "#10B981", bg: "#ECFDF5" },
  2: { label: "Caution", color: "#F59E0B", bg: "#FFFBEB" },
  3: { label: "Medium", color: "#F97316", bg: "#FFF7ED" },
  4: { label: "High", color: "#EF4444", bg: "#FEF2F2" },
  5: { label: "Critical", color: "#991B1B", bg: "#FEE2E2" },
};

function timeAgo(ts: string): string {
  const diff = (Date.now() - new Date(ts).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function IncidentsScreen() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<"all" | "ACTIVE" | "ACKED" | "CLOSED">("all");

  const fetchIncidents = useCallback(async () => {
    try {
      const data = await api.listIncidents(filter !== "all" ? { status: filter } : undefined);
      setIncidents(data);
    } catch {
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchIncidents();
    const unsub = connectWebSocket((data) => {
      if (data.type === "INCIDENT_CREATED" || data.type === "SEVERITY_TICK") {
        fetchIncidents();
      }
    });
    const interval = setInterval(fetchIncidents, 5000);
    return () => {
      unsub();
      clearInterval(interval);
    };
  }, [fetchIncidents]);

  const handleAcknowledge = async (id: string) => {
    Alert.alert("Acknowledge Incident", "Mark this incident as acknowledged?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Acknowledge",
        onPress: async () => {
          try {
            await api.ackIncident(id);
            fetchIncidents();
          } catch {}
        },
      },
    ]);
  };

  const filtered = incidents;
  const activeCount = incidents.filter((i) => i.status === "ACTIVE").length;

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#4F46E5" />
        <Text style={styles.loadingText}>Loading incidents...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Incidents</Text>
        <Text style={styles.subtitle}>
          {activeCount} active · {incidents.length} total
        </Text>
      </View>

      <View style={styles.filterRow}>
        {(["all", "ACTIVE", "ACKED", "CLOSED"] as const).map((f) => (
          <TouchableOpacity
            key={f}
            style={[styles.filterBtn, filter === f && styles.filterBtnActive]}
            onPress={() => setFilter(f)}
          >
            <Text style={[styles.filterText, filter === f && styles.filterTextActive]}>
              {f === "all" ? "All" : f === "ACKED" ? "Ack'd" : f.charAt(0) + f.slice(1).toLowerCase()}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {filtered.length === 0 ? (
        <View style={styles.empty}>
          <Text style={styles.emptyIcon}>✅</Text>
          <Text style={styles.emptyText}>No incidents</Text>
          <Text style={styles.emptyHint}>All clear! No incidents to report.</Text>
        </View>
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(item) => item.incident_id}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchIncidents(); }} tintColor="#4F46E5" />}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => {
            const sev = severityConfig[item.severity_current] || severityConfig[3];
            const isHigh = item.severity_current >= 4;
            const threat = isHigh ? "Person on the floor" : "Person on the edge";
            return (
              <View style={[styles.card, { borderLeftColor: sev.color }]}>
                <View style={styles.cardHeader}>
                  <View style={[styles.sevBadge, { backgroundColor: sev.bg }]}>
                    <Text style={[styles.sevText, { color: sev.color }]}>
                      Sev {item.severity_current} · {sev.label}
                    </Text>
                  </View>
                  <Text style={styles.timeText}>{timeAgo(item.created_at)}</Text>
                </View>

                <Text style={styles.threatText}>{threat}</Text>

                {item.reasons_current?.length > 0 && (
                  <Text style={styles.reasonText} numberOfLines={2}>
                    {item.reasons_current[0]}
                  </Text>
                )}

                <View style={styles.cardFooter}>
                  <View
                    style={[
                      styles.statusBadge,
                      {
                        backgroundColor:
                          item.status === "ACTIVE" ? "#FEF2F2" : item.status === "ACKED" ? "#EFF6FF" : "#F1F5F9",
                      },
                    ]}
                  >
                    <Text
                      style={[
                        styles.statusText,
                        {
                          color:
                            item.status === "ACTIVE" ? "#DC2626" : item.status === "ACKED" ? "#2563EB" : "#64748B",
                        },
                      ]}
                    >
                      {item.status === "ACKED" ? "Acknowledged" : item.status}
                    </Text>
                  </View>
                  {item.status === "ACTIVE" && (
                    <TouchableOpacity style={styles.ackBtn} onPress={() => handleAcknowledge(item.incident_id)}>
                      <Text style={styles.ackBtnText}>Acknowledge</Text>
                    </TouchableOpacity>
                  )}
                </View>
              </View>
            );
          }}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F8FAFC" },
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#F8FAFC" },
  loadingText: { marginTop: 12, color: "#64748B", fontSize: 14 },
  header: { paddingHorizontal: 20, paddingTop: 60, paddingBottom: 12, backgroundColor: "#4F46E5" },
  title: { fontSize: 28, fontWeight: "800", color: "#FFFFFF" },
  subtitle: { fontSize: 14, color: "#C7D2FE", marginTop: 4 },
  filterRow: {
    flexDirection: "row",
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 8,
    backgroundColor: "#FFFFFF",
    borderBottomWidth: 1,
    borderBottomColor: "#E2E8F0",
  },
  filterBtn: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: "#F1F5F9",
  },
  filterBtnActive: { backgroundColor: "#4F46E5" },
  filterText: { fontSize: 13, fontWeight: "600", color: "#64748B" },
  filterTextActive: { color: "#FFFFFF" },
  list: { paddingHorizontal: 16, paddingTop: 12 },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  sevBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  sevText: { fontSize: 12, fontWeight: "700" },
  timeText: { fontSize: 12, color: "#94A3B8" },
  threatText: { fontSize: 16, fontWeight: "600", color: "#1E293B", marginBottom: 4 },
  reasonText: { fontSize: 13, color: "#64748B", marginBottom: 12 },
  cardFooter: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  statusBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  statusText: { fontSize: 12, fontWeight: "600" },
  ackBtn: {
    backgroundColor: "#4F46E5",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 10,
  },
  ackBtnText: { color: "#FFFFFF", fontSize: 13, fontWeight: "600" },
  empty: { flex: 1, justifyContent: "center", alignItems: "center", padding: 40 },
  emptyIcon: { fontSize: 48, marginBottom: 16 },
  emptyText: { fontSize: 18, fontWeight: "600", color: "#334155" },
  emptyHint: { fontSize: 14, color: "#64748B", marginTop: 8 },
});
