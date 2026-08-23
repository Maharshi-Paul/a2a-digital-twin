"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import type { WSData, DecisionCommentary } from "../types";
import { WS_URL } from "../api/client";

/**
 * Custom hook for WebSocket connection with auto-reconnect and orjson binary support.
 */
export function useWebSocket() {
    const [data, setData] = useState<WSData | null>(null);
    const [connected, setConnected] = useState(false);
    const [commentaries, setCommentaries] = useState<DecisionCommentary[]>([]);
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimer = useRef<NodeJS.Timeout | null>(null);
    const reconnectRef = useRef<() => void>(() => undefined);

    const handleParsed = useCallback((parsed: Record<string, unknown>) => {
        if (parsed.type === "state_update") {
            setData(parsed as unknown as WSData);
        } else if (parsed.type === "decision_commentary") {
            setCommentaries((prev) => [
                ...prev.slice(-9),
                {
                    order_id: parsed.order_id as number,
                    external_id: parsed.external_id as string,
                    commentary: parsed.commentary as string,
                    timestamp: parsed.timestamp as string,
                },
            ]);
        }
    }, []);

    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onopen = () => {
            setConnected(true);
        };

        ws.onmessage = (e) => {
            try {
                const parsed =
                    e.data instanceof Blob
                        ? JSON.parse(
                            new TextDecoder().decode(e.data as unknown as ArrayBuffer)
                        )
                        : JSON.parse(e.data);
                handleParsed(parsed);
            } catch {
                // Handle binary orjson payloads from Blob
                if (e.data instanceof Blob) {
                    (e.data as Blob).text().then((text) => {
                        try {
                            const parsed = JSON.parse(text);
                            handleParsed(parsed);
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
    }, [handleParsed]);

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

    return { data, connected, commentaries };
}
