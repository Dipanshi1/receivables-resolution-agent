import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import CaseDetailPage from '../app/cases/[id]/page';
import * as api from '../lib/api';

jest.mock('../lib/api', () => ({
  fetchCase: jest.fn(),
  fetchCaseAudit: jest.fn(),
  formatCurrency: (val: number) => `₹${val/100}`
}));

describe('CaseDetailPage', () => {
  it('renders case details', async () => {
    (api.fetchCase as jest.Mock).mockResolvedValue({
      id: 'test-case-id',
      status: 'OVERDUE',
      invoice_id: 'inv-01',
      customer_id: 'cust-01',
      claimed_disputed_amount_minor: 100000,
      remaining_amount_minor: 100000,
      recovered_amount_minor: 0,
      collectible_amount_minor: 100000,
      safely_recoverable_amount_minor: 100000,
      verified_disputed_amount_minor: null,
    });
    
    (api.fetchCaseAudit as jest.Mock).mockResolvedValue({
      data: [],
      total: 0
    });

    render(<CaseDetailPage params={{ id: 'test-case-id' }} />);
    
    await waitFor(() => {
      expect(screen.getByText('test-case-id')).toBeInTheDocument();
    });

    expect(screen.getByText('OVERDUE')).toBeInTheDocument();
    expect(screen.getByText('Run Triage')).toBeInTheDocument();
  });
});
