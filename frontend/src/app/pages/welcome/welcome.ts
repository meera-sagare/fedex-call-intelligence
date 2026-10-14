import { CurrencyPipe, DatePipe } from '@angular/common';
import { Component, computed, effect, inject, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { catchError, debounceTime, of } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { CollectorContextService } from '../../core/collector-context.service';
import { Collector, CustomerSummary, PortfolioInsights } from '../../core/models';
import { statusClass } from '../../shared/format';

const STATUSES = ['Active', 'Past Due', 'In Dispute', 'Promise to Pay', 'Collections Hold', 'Closed'];

@Component({
  selector: 'app-welcome',
  imports: [CurrencyPipe, DatePipe],
  templateUrl: './welcome.html',
  styleUrl: './welcome.scss',
})
export class Welcome {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  protected readonly ctx = inject(CollectorContextService);

  protected readonly statuses = STATUSES;
  protected readonly statusClass = statusClass;

  protected readonly collectors = signal<Collector[]>([]);
  protected readonly customers = signal<CustomerSummary[]>([]);
  protected readonly insights = signal<PortfolioInsights | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly search = signal('');
  protected readonly status = signal('');

  protected readonly collector = computed(() =>
    this.collectors().find((c) => c.id === this.ctx.collectorId()),
  );
  protected readonly firstName = computed(() => this.collector()?.full_name.split(' ')[0] ?? '');
  protected readonly sentimentTotal = computed(() =>
    Object.values(this.insights()?.sentiment_breakdown ?? {}).reduce((a, b) => a + b, 0),
  );

  private readonly debouncedSearch = toSignal(toObservable(this.search).pipe(debounceTime(250)), {
    initialValue: '',
  });

  constructor() {
    this.api.collectors().subscribe({
      next: (list) => {
        this.collectors.set(list);
        const current = this.ctx.collectorId();
        if (list.length && !list.some((c) => c.id === current)) this.ctx.select(list[0].id);
        if (!list.length) this.loading.set(false);
      },
      error: () => {
        this.error.set('Unable to reach the Call Intelligence service. Check that the backend is running.');
        this.loading.set(false);
      },
    });

    effect(() => {
      const id = this.ctx.collectorId();
      if (!id || !this.collectors().length) return;
      const search = this.debouncedSearch();
      const status = this.status();
      this.loading.set(true);
      this.api
        .customersFor(id, search, status)
        .pipe(catchError(() => (this.error.set('Could not load customers.'), of([]))))
        .subscribe((list) => {
          this.customers.set(list);
          this.loading.set(false);
        });
    });

    effect(() => {
      const id = this.ctx.collectorId();
      if (!id || !this.collectors().length) return;
      this.api
        .insights(id)
        .pipe(catchError(() => of(null)))
        .subscribe((data) => this.insights.set(data));
    });
  }

  protected onCollectorChange(value: string): void {
    this.ctx.select(Number(value));
  }

  protected open(customerId: number): void {
    this.router.navigate(['/customers', customerId]);
  }

  protected sentimentPct(count: number): number {
    const total = this.sentimentTotal();
    return total ? Math.round((count / total) * 100) : 0;
  }
}
