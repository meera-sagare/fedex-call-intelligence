import { CurrencyPipe, DatePipe, DecimalPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, ElementRef, effect, inject, input, signal, viewChild } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ApiService } from '../../core/api.service';
import { CallLog, CallLogListItem, Customer } from '../../core/models';
import { duration, statusClass } from '../../shared/format';

@Component({
  selector: 'app-customer-detail',
  imports: [CurrencyPipe, DatePipe, DecimalPipe, RouterLink],
  templateUrl: './customer-detail.html',
  styleUrl: './customer-detail.scss',
})
export class CustomerDetail {
  private readonly api = inject(ApiService);

  /** Route parameter `:id`. */
  readonly id = input.required<string>();

  protected readonly statusClass = statusClass;
  protected readonly duration = duration;
  protected readonly today = new Date();

  protected readonly customer = signal<Customer | null>(null);
  protected readonly calls = signal<CallLogListItem[]>([]);
  protected readonly selected = signal<CallLog | null>(null);
  protected readonly selectedId = signal<number | null>(null);
  protected readonly analyzing = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly showTranscript = signal(false);
  protected readonly copied = signal(false);

  protected readonly showUpload = signal(false);
  protected readonly uploading = signal(false);
  protected readonly uploadError = signal<string | null>(null);
  protected readonly audioFile = signal<File | null>(null);
  protected readonly transcriptText = signal('');
  protected readonly direction = signal<'Inbound' | 'Outbound'>('Outbound');

  private readonly analysisPanel = viewChild<ElementRef<HTMLElement>>('analysisPanel');

  constructor() {
    effect(() => {
      const id = Number(this.id());
      this.reset();
      this.api.customer(id).subscribe({
        next: (c) => {
          this.customer.set(c);
          document.title = `${c.full_name} | ABC Call Intelligence`;
        },
        error: (e: HttpErrorResponse) =>
          this.error.set(e.status === 404 ? 'Customer not found.' : 'Could not load customer details.'),
      });
      this.loadCalls(id);
    });
  }

  protected openCall(call: CallLogListItem): void {
    this.selectedId.set(call.id);
    this.selected.set(null);
    this.showTranscript.set(false);
    this.analyzing.set(call.analysis_status !== 'Completed');
    this.api.callLog(call.id).subscribe({
      next: (full) => this.showAnalysis(full),
      error: () => {
        this.analyzing.set(false);
        this.error.set('Could not load the call log.');
      },
    });
  }

  protected reanalyze(): void {
    const current = this.selected();
    if (!current) return;
    this.analyzing.set(true);
    this.api.reanalyze(current.id).subscribe({
      next: (full) => this.showAnalysis(full),
      error: () => {
        this.analyzing.set(false);
        this.error.set('Re-analysis failed. Please try again.');
      },
    });
  }

  protected async copyNotes(): Promise<void> {
    const notes = this.selected()?.interaction_notes;
    if (!notes) return;
    try {
      await navigator.clipboard.writeText(notes);
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 2000);
    } catch {
      /* clipboard blocked - notes remain selectable on screen */
    }
  }

  protected onAudioSelected(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0] ?? null;
    this.audioFile.set(file);
  }

  protected submitCall(): void {
    const customer = this.customer();
    if (!customer || (!this.audioFile() && !this.transcriptText().trim())) {
      this.uploadError.set('Attach a call recording or paste the transcript.');
      return;
    }
    this.uploading.set(true);
    this.uploadError.set(null);
    this.api
      .createCallLog(customer.id, {
        audio: this.audioFile(),
        transcript: this.transcriptText(),
        direction: this.direction(),
      })
      .subscribe({
        next: (call) => {
          this.uploading.set(false);
          this.showUpload.set(false);
          this.audioFile.set(null);
          this.transcriptText.set('');
          this.loadCalls(customer.id);
          this.selectedId.set(call.id);
          this.showAnalysis(call);
        },
        error: (e: HttpErrorResponse) => {
          this.uploading.set(false);
          this.uploadError.set(e.error?.detail ?? 'Upload failed. Please try again.');
        },
      });
  }

  protected scorePosition(score: number | null): number {
    return score === null ? 50 : Math.round(((score + 1) / 2) * 100);
  }

  private showAnalysis(full: CallLog): void {
    this.analyzing.set(false);
    this.selected.set(full);
    this.calls.update((list) =>
      list.map((c) =>
        c.id === full.id
          ? { ...c, sentiment: full.sentiment, call_outcome: full.call_outcome, analysis_status: full.analysis_status }
          : c,
      ),
    );
    queueMicrotask(() =>
      this.analysisPanel()?.nativeElement.scrollIntoView({ behavior: 'smooth', block: 'start' }),
    );
  }

  private loadCalls(customerId: number): void {
    this.api.callLogs(customerId).subscribe({
      next: (list) => this.calls.set(list),
      error: () => this.error.set('Could not load call logs.'),
    });
  }

  private reset(): void {
    this.customer.set(null);
    this.calls.set([]);
    this.selected.set(null);
    this.selectedId.set(null);
    this.error.set(null);
  }
}
