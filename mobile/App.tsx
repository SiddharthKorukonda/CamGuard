import React from "react";
import { StatusBar } from "expo-status-bar";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { Ionicons } from "@expo/vector-icons";

import CameraScreen from "./src/screens/CameraScreen";
import IncidentsScreen from "./src/screens/IncidentsScreen";
import ChatBotScreen from "./src/screens/ChatBotScreen";

const Tab = createBottomTabNavigator();

export default function App() {
  return (
    <NavigationContainer>
      <StatusBar style="light" />
      <Tab.Navigator
        screenOptions={({ route }) => ({
          headerShown: false,
          tabBarStyle: {
            backgroundColor: "#FFFFFF",
            borderTopColor: "#E2E8F0",
            height: 85,
            paddingBottom: 28,
            paddingTop: 8,
          },
          tabBarActiveTintColor: "#4F46E5",
          tabBarInactiveTintColor: "#94A3B8",
          tabBarLabelStyle: { fontSize: 12, fontWeight: "600" },
          tabBarIcon: ({ focused, color, size }) => {
            let iconName: keyof typeof Ionicons.glyphMap = "camera";
            if (route.name === "Camera") iconName = focused ? "videocam" : "videocam-outline";
            else if (route.name === "Incidents") iconName = focused ? "warning" : "warning-outline";
            else if (route.name === "AI Bot") iconName = focused ? "chatbubbles" : "chatbubbles-outline";
            return <Ionicons name={iconName} size={size} color={color} />;
          },
        })}
      >
        <Tab.Screen name="Camera" component={CameraScreen} />
        <Tab.Screen
          name="Incidents"
          component={IncidentsScreen}
          options={{
            tabBarBadge: undefined,
          }}
        />
        <Tab.Screen name="AI Bot" component={ChatBotScreen} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
