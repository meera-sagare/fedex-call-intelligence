import { Injectable, signal } from '@angular/core';

const STORAGE_KEY = 'fci.collectorId';

/** Remembers which collector is using the app (stand-in for SSO identity). */
@Injectable({ providedIn: 'root' })
export class CollectorContextService {
  readonly collectorId = signal<number | null>(this.read());

  select(id: number): void {
    this.collectorId.set(id);
    try {
      localStorage.setItem(STORAGE_KEY, String(id));
    } catch {
      /* storage unavailable - selection still works for this session */
    }
  }

  private read(): number | null {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? Number(raw) : null;
    } catch {
      return null;
    }
  }
}
