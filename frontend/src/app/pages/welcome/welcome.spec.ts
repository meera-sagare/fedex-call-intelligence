import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { Welcome } from './welcome';

const collectors = [{ id: 1, full_name: 'Priya Sharma', email: 'p@x.com', region: 'East' }];
const customers = [
  {
    id: 7, account_number: 'ABC-1', full_name: 'Michael Turner', company_name: 'Turner Supply',
    phone_number: '555', status: 'Past Due', ar_balance: '1000.00', overdue_amount: '500.00',
    days_past_due: 30, risk_level: 'High', last_contact_date: null,
  },
];

describe('Welcome', () => {
  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      imports: [Welcome],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
  });

  it('shows the selected collector greeting and their customers, and opens a customer on click', async () => {
    const fixture = TestBed.createComponent(Welcome);
    const http = TestBed.inject(HttpTestingController);
    const router = TestBed.inject(Router);
    const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);

    http.expectOne('/api/collectors').flush(collectors);
    await fixture.whenStable();
    http.expectOne((r) => r.url === '/api/collectors/1/customers').flush(customers);
    http.expectOne((r) => r.url === '/api/insights/portfolio').flush(null);
    await fixture.whenStable();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('h1')?.textContent).toContain('Welcome, Priya');
    const card = el.querySelector<HTMLButtonElement>('button.customer');
    expect(card?.textContent).toContain('Michael Turner');
    expect(card?.textContent).toContain('Past Due');

    card!.click();
    expect(navigate).toHaveBeenCalledWith(['/customers', 7]);
    http.verify();
  });
});
