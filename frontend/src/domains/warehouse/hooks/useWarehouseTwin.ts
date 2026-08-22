"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { firebaseConfigured } from "@/lib/firebase";
import {
  runSimulationTick,
  seedWarehouseTwin,
  setSimulationRunning,
  subscribeToWarehouseTwin,
} from "../firestore-twin";
import { EMPTY_WAREHOUSE_STATE, type WarehouseTwinState } from "../live-twin";

export function useWarehouseTwin() {
  const [state, setState] = useState<WarehouseTwinState>(EMPTY_WAREHOUSE_STATE);
  const [connectionError, setConnectionError] = useState<string | null>(
    firebaseConfigured ? null : "Firebase configuration is missing.",
  );
  const [connected, setConnected] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isSeeding, setIsSeeding] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tickInProgressRef = useRef(false);

  useEffect(() => {
    if (!firebaseConfigured) return;

    const unsubscribe = subscribeToWarehouseTwin(
      (update) => {
        setState((current) => ({ ...current, ...update }));
        setConnected(true);
        setConnectionError(null);
      },
      (error) => {
        setConnected(false);
        setConnectionError(error.message);
      },
    );
    return unsubscribe;
  }, []);

  const stop = useCallback(async () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    try {
      await setSimulationRunning(false);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to stop the simulation.");
    }
  }, []);

  const runTick = useCallback(async (): Promise<boolean> => {
    if (tickInProgressRef.current) return false;
    tickInProgressRef.current = true;
    try {
      await runSimulationTick();
      setActionError(null);
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "The simulation tick failed.";
      setActionError(message);
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      try {
        await setSimulationRunning(false);
      } catch {
        // Preserve the useful original error if the network is also unavailable.
      }
      return false;
    } finally {
      tickInProgressRef.current = false;
    }
  }, []);

  const start = useCallback(async () => {
    if (timerRef.current) return;
    setIsStarting(true);
    setActionError(null);
    try {
      const tickSucceeded = await runTick();
      if (tickSucceeded && !timerRef.current && !tickInProgressRef.current) {
        timerRef.current = setInterval(() => void runTick(), 2_500);
      }
    } finally {
      setIsStarting(false);
    }
  }, [runTick]);

  const seed = useCallback(async () => {
    setIsSeeding(true);
    setActionError(null);
    try {
      if (timerRef.current) await stop();
      await seedWarehouseTwin();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to seed Firestore.");
    } finally {
      setIsSeeding(false);
    }
  }, [stop]);

  useEffect(() => () => {
    if (timerRef.current) clearInterval(timerRef.current);
  }, []);

  return {
    state,
    connected,
    connectionError,
    actionError,
    isSeeding,
    isStarting,
    seed,
    start,
    stop,
  };
}
