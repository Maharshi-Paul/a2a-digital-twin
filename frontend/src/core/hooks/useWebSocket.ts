"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import type { WSData, DecisionCommentary } from "../types";
import { WS_URL, api } from "../api/client";

/**
 * Custom hook for WebSocket connection with:
 * - Cold-start health check / wake probe (Render free tier)
 * - Exponential backoff reconnect with jitter
 * - Heartbeat ping-pong every 25s
 * - orjson binary / Blob parsing support
 */
export function useWebSocket() {
    const [data, setData] = useState<WSData | null>(null);
    const [connected, setConnected] = useState(false);
    const [isWakingUp, setIsWakingUp] = useState(false);
    const [connectionError, setConnectionError] = useState<string | null>(null);
    const [commentaries, setCommentaries] = useState<DecisionCommentary[]>([]);

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimer = useRef<NodeJS.Timeout | null>(null);
    const heartbeatTimer = useRef<NodeJS.Timeout | null>(null);
    const attemptsRef = useRef(0);
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

    const stopHeartbeat = useCallback(() => {
        if (heartbeatTimer.current) {
            clearInterval(heartbeatTimer.current);
            heartbeatTimer.current = null;
        }
    }, []);

    const startHeartbeat = useCallback(() => {
        stopHeartbeat();
        // Send a ping frame every 25 seconds to keep connection alive through cloud proxies
        heartbeatTimer.current = setInterval(() => {
            if (wsRef.current?.readyState === WebSocket.OPEN) {
                try {
                    wsRef.current.send("ping");
                } catch {
                    /* ignore send error; onclose will handle reconnect */
                }
            }
        }, 25000);
    }, [stopHeartbeat]);

    const connect = useCallback(() => {
        if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
            return;
        }

        try {
            const ws = new WebSocket(WS_URL);
            wsRef.current = ws;

            ws.onopen = () => {
                setConnected(true);
                setIsWakingUp(false);
                setConnectionError(null);
                attemptsRef.current = 0;
                startHeartbeat();
            };

            ws.onmessage = (e) => {
                if (typeof e.data === "string" && e.data === "pong") {
                    return; // Heartbeat response
                }
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
                stopHeartbeat();

                // Exponential backoff: 1s, 2s, 4s, 8s, max 15s + jitter
                const backoff = Math.min(1000 * Math.pow(1.8, attemptsRef.current), 15000) + Math.random() * 500;
                attemptsRef.current++;

                if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
                reconnectTimer.current = setTimeout(() => reconnectRef.current(), backoff);
            };

            ws.onerror = () => {
                setConnectionError("WebSocket connection error");
                ws.close();
            };
        } catch (err) {
            setConnected(false);
            setConnectionError(err instanceof Error ? err.message : "Failed to open WebSocket");
            const backoff = Math.min(1000 * Math.pow(1.8, attemptsRef.current), 15000) + Math.random() * 500;
            attemptsRef.current++;
            if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
            reconnectTimer.current = setTimeout(() => reconnectRef.current(), backoff);
        }
    }, [handleParsed, startHeartbeat, stopHeartbeat]);

    useEffect(() => {
        reconnectRef.current = connect;
    }, [connect]);

    // Cold-start probe: ping /health to wake Render/Railway instances
    useEffect(() => {
        let isCancelled = false;
        let pollTimer: NodeJS.Timeout | null = null;

        async function probeBackend() {
            try {
                const res = await api.health();
                if (res.status === "healthy" && !isCancelled) {
                    setIsWakingUp(false);
                    connect();
                }
            } catch {
                if (!isCancelled) {
                    setIsWakingUp(true);
                    // Poll health endpoint every 4 seconds until backend wakes up
                    pollTimer = setTimeout(probeBackend, 4000);
                }
            }
        }

        probeBackend();

        return () => {
            isCancelled = true;
            if (pollTimer) clearTimeout(pollTimer);
            if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
            stopHeartbeat();
            wsRef.current?.close();
        };
    }, [connect, stopHeartbeat]);

    return { data, connected, isWakingUp, connectionError, commentaries };
}
