'use client';

import React, { useEffect, useState } from 'react';
import { fetchHealthStatus, getApiBaseUrl, HealthResponse } from '../lib/api';

type StatusState = 'checking' | 'connected' | 'unavailable';

export function BackendStatus() {
  const [status, setStatus] = useState<StatusState>('checking');
  const [data, setData] = useState<HealthResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<string | null>(null);

  const checkStatus = async () => {
    setStatus('checking');
    setErrorMessage(null);

    const result = await fetchHealthStatus();
    setLastChecked(new Date().toLocaleTimeString());

    if (result.connected && result.data) {
      setStatus('connected');
      setData(result.data);
      setErrorMessage(null);
    } else {
      setStatus('unavailable');
      setData(null);
      setErrorMessage(result.error || 'Connection refused or unavailable');
    }
  };

  useEffect(() => {
    checkStatus();
  }, []);

  const baseUrl = getApiBaseUrl();

  return (
    <div className={`status-panel ${status}`}>
      <div className="status-panel-header">
        <div className="status-indicator-group">
          <span className={`status-dot ${status}`} aria-hidden="true" />
          <h2 className="status-title">
            {status === 'checking' && 'Checking…'}
            {status === 'connected' && 'Backend Connected'}
            {status === 'unavailable' && 'Backend Unavailable'}
          </h2>
        </div>
        <button
          type="button"
          onClick={checkStatus}
          disabled={status === 'checking'}
          className="recheck-button"
        >
          {status === 'checking' ? 'Checking…' : 'Recheck Connection'}
        </button>
      </div>

      <div className="status-details">
        <div className="detail-row">
          <span className="detail-key">Backend Target URL:</span>
          <code className="detail-value">{baseUrl}</code>
        </div>
        <div className="detail-row">
          <span className="detail-key">Health Endpoint:</span>
          <code className="detail-value">GET /v1/health</code>
        </div>
        {status === 'connected' && data && (
          <div className="detail-row">
            <span className="detail-key">Response Status:</span>
            <span className="detail-badge success">{data.status}</span>
          </div>
        )}
        {status === 'unavailable' && errorMessage && (
          <div className="detail-row">
            <span className="detail-key">Failure Reason:</span>
            <span className="detail-badge error">{errorMessage}</span>
          </div>
        )}
        {lastChecked && (
          <div className="detail-row">
            <span className="detail-key">Last Checked:</span>
            <span className="detail-time">{lastChecked}</span>
          </div>
        )}
      </div>
    </div>
  );
}
