import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { CustomerDetail } from './customer-detail';

const customer = {
  id: 3, collector_id: 1, account_number: 'ABC-3', full_name: 'Sarah Mitchell', company_name: 'Brightline',
  phone_number: '+1 617', alternate_phone_number: '+1 618', email: 's@b.com', address: '1 Kendall Sq',
  shipping_address: 'Dock 1', home_address: '14 Elm St', office_address: 'Suite 300', status: 'In Dispute',
  ar_balance: '100.00', overdue_amount: '50.00', days_past_due: 60, risk_level: 'High', last_contact_date: null,
};
const listItem = {
  id: 11, call_datetime: '2026-10-13T11:00:00Z', duration_seconds: 655, direction: 'Outbound',
  sentiment: null, call_outcome: null, analysis_status: 'Pending', audio_filename: null,
};
const analyzed = {
  ...listItem, customer_id: 3, collector_id: 1, transcript: 'Customer: overcharged',
  call_log_summary: 'Customer disputed surcharges.', interaction_notes: '- Dispute opened.',
  sentiment: 'Negative', sentiment_score: -0.6, call_outcome: 'Dispute Raised', analysis_status: 'Completed',
  payment_commitments: [], risks: [{ category: 'Dispute', description: 'Surcharge dispute', severity: 'High' }],
  follow_up_actions: [], dispute_raised: true, analysis_engine: 'rules', analysis_error: null,
  analyzed_at: '2026-10-14T10:00:00Z',
};

describe('CustomerDetail', () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn(); // not implemented by jsdom
    TestBed.configureTestingModule({
      imports: [CustomerDetail],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
  });

  async function render() {
    const fixture = TestBed.createComponent(CustomerDetail);
    fixture.componentRef.setInput('id', '3');
    const http = TestBed.inject(HttpTestingController);
    await fixture.whenStable();
    http.expectOne('/api/customers/3').flush(customer);
    http.expectOne('/api/customers/3/call-logs').flush([listItem]);
    await fixture.whenStable();
    return { fixture, http, el: fixture.nativeElement as HTMLElement };
  }

  it('shows the customer name in the banner and every contact field', async () => {
    const { el } = await render();
    expect(el.querySelector('.banner h1')?.textContent).toContain('Sarah Mitchell');
    const labels = Array.from(el.querySelectorAll('dt')).map((d) => d.textContent?.trim());
    expect(labels).toEqual([
      'Full name', 'Status', 'Phone number', 'Alternate phone number', 'Email',
      'Address', 'Shipping address', 'Home address', 'Office address',
    ]);
    expect(el.querySelector('.calls')?.textContent).toContain('Not yet analyzed');
  });

  it('loads the summary and analysis when a call log is clicked', async () => {
    const { fixture, http, el } = await render();
    el.querySelector<HTMLButtonElement>('button.call')!.click();
    await fixture.whenStable();
    expect(el.querySelector('.analyzing')).not.toBeNull();

    http.expectOne('/api/call-logs/11').flush(analyzed);
    await fixture.whenStable();
    expect(el.querySelector('.summary')?.textContent).toContain('Customer disputed surcharges.');
    expect(el.querySelector('.notes')?.textContent).toContain('- Dispute opened.');
    expect(el.querySelector('.analysis')?.textContent).toContain('Dispute raised');
    expect(el.querySelector('.calls')?.textContent).toContain('Dispute Raised');
    http.verify();
  });

  it('requires a recording or transcript before logging a call', async () => {
    const { fixture, el } = await render();
    el.querySelector<HTMLButtonElement>('.side-col .btn')!.click();
    await fixture.whenStable();
    el.querySelector<HTMLFormElement>('form.upload')!.dispatchEvent(new Event('submit'));
    await fixture.whenStable();
    expect(el.querySelector('.error-text')?.textContent).toContain('Attach a call recording');
  });
});
