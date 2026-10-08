// Monitoring feature hooks

import { useState, useEffect, useCallback } from 'react';
import { monitoringApi } from './api';
import type { OverviewResponse, ScanHistoryResponse, SubsectionsResponse } from './types';

// Hook for fetching monitoring overview
export function useMonitoringOverview(days = 7, platform = 'web') {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await monitoringApi.overview(days, platform);
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [days, platform]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

// Hook for fetching monitoring health
export function useMonitoringHealth(days = 7, platform = 'web') {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await monitoringApi.health(days, platform);
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [days, platform]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

// Hook for fetching monitoring feedback
export function useMonitoringFeedback(days = 30) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await monitoringApi.feedback(days);
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

// Hook for fetching monitoring history
export function useMonitoringHistory(subsection = null, limit = 50) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await monitoringApi.history(subsection, limit);
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [subsection, limit]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

// Hook for fetching subsections
export function useMonitoringSubsections() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await monitoringApi.subsections();
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

// Hook for triggering a scan
export function useTriggerScan() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const trigger = async (subsection, windowDays = 7, model = null) => {
    setLoading(true);
    setError(null);
    try {
      const result = await monitoringApi.scan(subsection, { window_days: windowDays, model });
      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  return { trigger, loading, error };
}

// Hook for triggering rollup
export function useTriggerRollup() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const trigger = async (lookbackHours = 48) => {
    setLoading(true);
    setError(null);
    try {
      const result = await monitoringApi.rollup(lookbackHours);
      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  return { trigger, loading, error };
}

// Hook for fetching monetisation data
export function useMonitoringMonetisation(days = 30) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await monitoringApi.monetisation(days);
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}