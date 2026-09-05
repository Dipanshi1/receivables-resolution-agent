import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import DashboardPage from '../app/page';
import * as api from '../lib/api';

jest.mock('../lib/api', () => ({
  fetchCases: jest.fn(),
  formatCurrency: (val: number) => `₹${val/100}`
}));

describe('DashboardPage', () => {
  it('renders loading state initially', () => {
    (api.fetchCases as jest.Mock).mockReturnValue(new Promise(() => {}));
    render(<DashboardPage />);
    expect(screen.getByText('Loading dashboard...')).toBeInTheDocument();
  });

  it('renders dashboard with data', async () => {
    (api.fetchCases as jest.Mock).mockResolvedValue({
      data: [
        {
          id: '123', status: 'OVERDUE', remaining_amount_minor: 100000, recovered_amount_minor: 0
        }
      ],
      total: 1
    });

    render(<DashboardPage />);
    
    await waitFor(() => {
      expect(screen.getByText('Merchant Recovery Dashboard')).toBeInTheDocument();
    });

    expect(screen.getAllByText('₹1000')[0]).toBeInTheDocument();
    expect(screen.getByText('123')).toBeInTheDocument();
  });
});
