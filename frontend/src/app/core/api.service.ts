import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  CallLog,
  CallLogListItem,
  Collector,
  Customer,
  CustomerSummary,
  PortfolioInsights,
} from './models';

export interface NewCallLog {
  audio?: File | null;
  transcript?: string;
  direction: 'Inbound' | 'Outbound';
  durationSeconds?: number;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api';

  collectors(): Observable<Collector[]> {
    return this.http.get<Collector[]>(`${this.base}/collectors`);
  }

  customersFor(collectorId: number, search = '', status = ''): Observable<CustomerSummary[]> {
    let params = new HttpParams();
    if (search) params = params.set('search', search);
    if (status) params = params.set('status', status);
    return this.http.get<CustomerSummary[]>(`${this.base}/collectors/${collectorId}/customers`, { params });
  }

  customer(id: number): Observable<Customer> {
    return this.http.get<Customer>(`${this.base}/customers/${id}`);
  }

  callLogs(customerId: number): Observable<CallLogListItem[]> {
    return this.http.get<CallLogListItem[]>(`${this.base}/customers/${customerId}/call-logs`);
  }

  /** Fetches a call log; the backend analyzes it on first open. */
  callLog(id: number): Observable<CallLog> {
    return this.http.get<CallLog>(`${this.base}/call-logs/${id}`);
  }

  reanalyze(id: number): Observable<CallLog> {
    return this.http.post<CallLog>(`${this.base}/call-logs/${id}/analyze`, {});
  }

  createCallLog(customerId: number, call: NewCallLog): Observable<CallLog> {
    const form = new FormData();
    if (call.audio) form.append('audio', call.audio);
    if (call.transcript?.trim()) form.append('transcript', call.transcript.trim());
    form.append('direction', call.direction);
    form.append('duration_seconds', String(call.durationSeconds ?? 0));
    return this.http.post<CallLog>(`${this.base}/customers/${customerId}/call-logs`, form);
  }

  insights(collectorId?: number): Observable<PortfolioInsights> {
    const params = collectorId ? new HttpParams().set('collector_id', collectorId) : undefined;
    return this.http.get<PortfolioInsights>(`${this.base}/insights/portfolio`, { params });
  }
}
