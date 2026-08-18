"use client";

import { useState, useCallback } from "react";

/**
 * Generic async API call hook with loading/error states.
 */
export function useApi<T>() {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [data, setData] = useState<T | null>(null);

    const execute = useCallback(async (fn: () => Promise<T>): Promise<T | null> => {
        setLoading(true);
        setError(null);
        try {
            const result = await fn();
            setData(result);
            return result;
        } catch (err) {
            const message = err instanceof Error ? err.message : "An error occurred";
            setError(message);
            return null;
        } finally {
            setLoading(false);
        }
    }, []);

    return { data, loading, error, execute };
}
