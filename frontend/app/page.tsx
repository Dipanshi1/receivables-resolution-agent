import React from 'react';
import { BackendStatus } from '../components/BackendStatus';

export default function HomePage() {
  return (
    <div className="page-container">
      <section className="intro-card">
        <h2>Merchant Revenue Recovery System</h2>
        <p>
          AI-assisted B2B receivables resolution platform that diagnoses payment blockers,
          decomposes collectible amounts, and executes policy-gated recovery through Razorpay.
        </p>
      </section>

      <section className="status-section">
        <BackendStatus />
      </section>
    </div>
  );
}
