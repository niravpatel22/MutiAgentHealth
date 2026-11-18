import { render, screen } from '@testing-library/react';
import App from '../src/app/App.jsx';

describe('App', () => {
  it('renders the product name', () => {
    render(<App />);
    expect(screen.getByRole('heading', { name: 'CareOps Intelligence' })).toBeInTheDocument();
  });
});
