export function duration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s.toString().padStart(2, '0')}s`;
}

export function statusClass(value: string | null | undefined): string {
  return (value ?? '').toLowerCase().replace(/\s+/g, '-');
}
