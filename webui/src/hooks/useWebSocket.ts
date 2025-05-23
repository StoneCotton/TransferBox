import { useRef, useEffect, useState, useCallback } from "react";
import type { WebSocketMessage } from "../types";
import { WS_URL, WS_RECONNECT_DELAY } from "../constants";

interface UseWebSocketOptions {
  onMessage: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  sendMessage: (message: Record<string, unknown>) => void;
  disconnect: () => void;
}

/**
 * Custom hook for managing WebSocket connections
 * Handles connection, reconnection, and message routing
 */
export const useWebSocket = ({
  onMessage,
  onConnect,
  onDisconnect,
  onError,
}: UseWebSocketOptions): UseWebSocketReturn => {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Use refs to store the latest callbacks without causing re-renders
  const onMessageRef = useRef(onMessage);
  const onConnectRef = useRef(onConnect);
  const onDisconnectRef = useRef(onDisconnect);
  const onErrorRef = useRef(onError);

  // Update refs when callbacks change
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    onConnectRef.current = onConnect;
  }, [onConnect]);

  useEffect(() => {
    onDisconnectRef.current = onDisconnect;
  }, [onDisconnect]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  const connectWebSocket = useCallback(() => {
    // Don't connect if already connected
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      console.log("Connecting to WebSocket:", WS_URL);
      wsRef.current = new WebSocket(WS_URL);

      wsRef.current.onopen = () => {
        console.log("WebSocket connected");
        setIsConnected(true);
        onConnectRef.current?.();

        // Clear any reconnection timeout
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }
      };

      wsRef.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          onMessageRef.current(message);
        } catch (error) {
          console.error("Error parsing WebSocket message:", error);
        }
      };

      wsRef.current.onclose = () => {
        console.log("WebSocket disconnected");
        setIsConnected(false);
        onDisconnectRef.current?.();

        // Only attempt to reconnect if we haven't explicitly disconnected
        if (wsRef.current !== null) {
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log("Attempting to reconnect...");
            connectWebSocket();
          }, WS_RECONNECT_DELAY);
        }
      };

      wsRef.current.onerror = (error) => {
        console.error("WebSocket error:", error);
        onErrorRef.current?.(error);
      };
    } catch (error) {
      console.error("Error creating WebSocket:", error);
      onErrorRef.current?.(error as Event);
    }
  }, []); // Empty dependency array since we use refs for callbacks

  const sendMessage = useCallback((message: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn("WebSocket is not connected, cannot send message");
    }
  }, []);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null; // Set to null to prevent reconnection
    }
    setIsConnected(false);
  }, []);

  useEffect(() => {
    connectWebSocket();

    // Cleanup on unmount
    return () => {
      disconnect();
    };
  }, [connectWebSocket, disconnect]);

  return {
    isConnected,
    sendMessage,
    disconnect,
  };
};
