import React, { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  Image,
  ActivityIndicator,
} from "react-native";
import { api, connectWebSocket } from "../lib/api";

interface Camera {
  id: string;
  name: string;
  room_type: string;
  status: string;
  risk_score: number;
}

export default function CameraScreen() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedCamera, setSelectedCamera] = useState<string | null>(null);

  const fetchCameras = useCallback(async () => {
    try {
      const data = await api.listCameras();
      setCameras(data);
    } catch {
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchCameras();
    const unsub = connectWebSocket(() => fetchCameras());
    const interval = setInterval(fetchCameras, 10000);
    return () => {
      unsub();
      clearInterval(interval);
    };
  }, [fetchCameras]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchCameras();
  };

  const riskColor = (score: number) => {
    if (score > 0.7) return "#DC2626";
    if (score > 0.3) return "#F59E0B";
    return "#10B981";
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#4F46E5" />
        <Text style={styles.loadingText}>Loading cameras...</Text>
      </View>
    );
  }

  if (selectedCamera) {
    const cam = cameras.find((c) => c.id === selectedCamera);
    return (
      <View style={styles.container}>
        <View style={styles.streamHeader}>
          <TouchableOpacity onPress={() => setSelectedCamera(null)} style={styles.backBtn}>
            <Text style={styles.backText}>Back</Text>
          </TouchableOpacity>
          <Text style={styles.streamTitle}>{cam?.name || "Camera"}</Text>
        </View>
        <View style={styles.streamContainer}>
          <Image
            source={{ uri: api.cameraStreamUrl(selectedCamera) }}
            style={styles.stream}
            resizeMode="contain"
          />
        </View>
        <View style={styles.streamInfo}>
          <Text style={styles.infoLabel}>Room: {cam?.room_type}</Text>
          <Text style={styles.infoLabel}>
            Risk:{" "}
            <Text style={{ color: riskColor(cam?.risk_score || 0), fontWeight: "700" }}>
              {((cam?.risk_score || 0) * 100).toFixed(0)}%
            </Text>
          </Text>
          <View
            style={[
              styles.statusDot,
              { backgroundColor: cam?.status === "online" ? "#10B981" : "#9CA3AF" },
            ]}
          />
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Cameras</Text>
        <Text style={styles.subtitle}>{cameras.length} camera(s)</Text>
      </View>
      {cameras.length === 0 ? (
        <View style={styles.empty}>
          <Text style={styles.emptyIcon}>📷</Text>
          <Text style={styles.emptyText}>No cameras registered</Text>
          <Text style={styles.emptyHint}>Add cameras from the web dashboard</Text>
        </View>
      ) : (
        <FlatList
          data={cameras}
          keyExtractor={(item) => item.id}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#4F46E5" />}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <TouchableOpacity style={styles.card} onPress={() => setSelectedCamera(item.id)}>
              <View style={styles.cardRow}>
                <View
                  style={[
                    styles.statusIndicator,
                    { backgroundColor: item.status === "online" ? "#10B981" : "#9CA3AF" },
                  ]}
                />
                <View style={styles.cardInfo}>
                  <Text style={styles.cardTitle}>{item.name}</Text>
                  <Text style={styles.cardSubtitle}>{item.room_type}</Text>
                </View>
                <View style={styles.riskBadge}>
                  <Text style={[styles.riskText, { color: riskColor(item.risk_score) }]}>
                    {(item.risk_score * 100).toFixed(0)}%
                  </Text>
                </View>
                <Text style={styles.chevron}>›</Text>
              </View>
            </TouchableOpacity>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F8FAFC" },
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#F8FAFC" },
  loadingText: { marginTop: 12, color: "#64748B", fontSize: 14 },
  header: { paddingHorizontal: 20, paddingTop: 60, paddingBottom: 16, backgroundColor: "#4F46E5" },
  title: { fontSize: 28, fontWeight: "800", color: "#FFFFFF" },
  subtitle: { fontSize: 14, color: "#C7D2FE", marginTop: 4 },
  list: { paddingHorizontal: 16, paddingTop: 12 },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  cardRow: { flexDirection: "row", alignItems: "center" },
  statusIndicator: { width: 10, height: 10, borderRadius: 5, marginRight: 12 },
  cardInfo: { flex: 1 },
  cardTitle: { fontSize: 16, fontWeight: "600", color: "#1E293B" },
  cardSubtitle: { fontSize: 12, color: "#64748B", marginTop: 2 },
  riskBadge: {
    backgroundColor: "#F8FAFC",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
    marginRight: 8,
  },
  riskText: { fontSize: 14, fontWeight: "700" },
  chevron: { fontSize: 24, color: "#94A3B8" },
  empty: { flex: 1, justifyContent: "center", alignItems: "center", padding: 40 },
  emptyIcon: { fontSize: 48, marginBottom: 16 },
  emptyText: { fontSize: 18, fontWeight: "600", color: "#334155" },
  emptyHint: { fontSize: 14, color: "#64748B", marginTop: 8, textAlign: "center" },
  streamHeader: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingTop: 60,
    paddingBottom: 12,
    backgroundColor: "#4F46E5",
  },
  backBtn: { padding: 8 },
  backText: { color: "#FFFFFF", fontSize: 16, fontWeight: "600" },
  streamTitle: { fontSize: 18, fontWeight: "700", color: "#FFFFFF", marginLeft: 12 },
  streamContainer: {
    flex: 1,
    backgroundColor: "#000",
    justifyContent: "center",
    alignItems: "center",
  },
  stream: { width: "100%", height: "100%" },
  streamInfo: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingVertical: 16,
    backgroundColor: "#FFFFFF",
  },
  infoLabel: { fontSize: 14, color: "#475569" },
  statusDot: { width: 12, height: 12, borderRadius: 6 },
});
