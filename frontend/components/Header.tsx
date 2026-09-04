import React from 'react';

export function Header() {
  return (
    <header className="app-header">
      <div className="header-container">
        <div className="header-branding">
          <span className="brand-badge">Track 03 — AI Revenue Recovery</span>
          <h1 className="brand-title">Receivables Resolution Agent</h1>
        </div>
        <nav className="header-nav">
          <span className="nav-item active">System Overview</span>
        </nav>
      </div>
    </header>
  );
}
