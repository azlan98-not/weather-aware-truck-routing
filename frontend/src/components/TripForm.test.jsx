import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import TripForm from './TripForm';

describe('TripForm validation', () => {
  it('blocks submission and shows errors for an empty origin', () => {
    const onSubmit = vi.fn();
    render(<TripForm onSubmit={onSubmit} loading={false} />);
    fireEvent.change(screen.getByLabelText('Origin'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: /generate routes/i }));
    expect(screen.getByText(/enter an origin/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('rejects a non-positive load weight', () => {
    const onSubmit = vi.fn();
    render(<TripForm onSubmit={onSubmit} loading={false} />);
    fireEvent.change(screen.getByLabelText(/load weight/i), { target: { value: '-5' } });
    fireEvent.click(screen.getByRole('button', { name: /generate routes/i }));
    expect(screen.getByText(/load weight must be positive/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('submits a well-formed analyze request for valid input', () => {
    const onSubmit = vi.fn();
    render(<TripForm onSubmit={onSubmit} loading={false} />);
    fireEvent.change(screen.getByLabelText('Origin'), { target: { value: 'Chicago, IL' } });
    fireEvent.change(screen.getByLabelText('Destination'), { target: { value: 'St Louis, MO' } });
    fireEvent.change(screen.getByLabelText(/load weight/i), { target: { value: '35000' } });
    fireEvent.change(screen.getByLabelText(/checkpoint interval/i), { target: { value: '25' } });
    fireEvent.click(screen.getByRole('button', { name: /generate routes/i }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
    const request = onSubmit.mock.calls[0][0];
    expect(request.origin).toBe('Chicago, IL');
    expect(request.destination).toBe('St Louis, MO');
    expect(request.load_weight_lb).toBe(35000);
    expect(request.checkpoint_interval_miles).toBe(25);
    expect(typeof request.departure_datetime).toBe('string');
    expect(Number.isNaN(Date.parse(request.departure_datetime))).toBe(false);
  });

  it('disables the submit button while a request is processing', () => {
    render(<TripForm onSubmit={vi.fn()} loading />);
    expect(screen.getByRole('button', { name: /generating routes/i })).toBeDisabled();
  });
});
