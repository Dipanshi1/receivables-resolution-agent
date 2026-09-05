import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import CasesPage from '../app/cases/page';
import * as api from '../lib/api';

jest.mock('../lib/api', () => ({
  fetchCases: jest.fn(),
  formatCurrency: (val: number) => `₹${val/100}`
}));

describe('CasesPage', () => {
  it('renders cases list', async () => {
    (api.fetchCases as jest.Mock).mockResolvedValue({
      data: [
        {
          id: 'case-1', 
          invoice_id: 'inv-1',
          status: 'HUMAN_REVIEW', 
          remaining_amount_minor: 50000, 
          recovered_amount_minor: 0
        }
      ],
      total: 1
    });

    render(<CasesPage />);
    
    await waitFor(() => {
      expect(screen.getByText('Recovery Cases')).toBeInTheDocument();
    });

    expect(screen.getByText('case-1')).toBeInTheDocument();
    expect(screen.getByText('HUMAN_REVIEW')).toBeInTheDocument();
  });
});
