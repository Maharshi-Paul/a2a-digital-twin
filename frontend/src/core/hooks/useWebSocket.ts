"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import type { WSData } from "../types";
import { WS_URL } from "../api/client";

/**
 * Custom hook for WebSocket connection with auto-reconnect and orjson binary support.
 */
export function useWebSocket() {
    const [data, setData] = useState<WSData | null>(null);
    const [connected, setConnected] = useState(false);
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimer = useRef<NodeJS.Timeout | null>(null);
    const reconnectRef = useRef<() => void>(() => undefined);

    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onopen = () => {
            setConnected(true);
        };

        ws.onmessage = (e) => {
            try {
                const parsed: WSData =
                    e.data instanceof Blob
                        ? JSON.parse(
                            new TextDecoder().decode(e.data as unknown as ArrayBuffer)
                        )
                        : JSON.parse(e.data);
                if (parsed.type === "state_update") {
                    setData(parsed);
                }
            } catch {
                // Handle binary orjson payloads from Blob
                if (e.data instanceof Blob) {
                    (e.data as Blob).text().then((text) => {
                        try {
                            const parsed = JSON.parse(text);
                            if (parsed.type === "state_update") setData(parsed);
                        } catch {
                            /* ignore malformed */
                        }
                    });
                }
            }
        };

        ws.onclose = () => {
            setConnected(false);
            reconnectTimer.current = setTimeout(() => reconnectRef.current(), 3000);
        };

        ws.onerror = () => ws.close();
    }, []);

    useEffect(() => {
        reconnectRef.current = connect;
    }, [connect]);

    useEffect(() => {
        connect();
        return () => {
            wsRef.current?.close();
            if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
        };
    }, [connect]);

    return { data, connected };
}
