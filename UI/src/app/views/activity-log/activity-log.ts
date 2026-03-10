import { ChangeDetectorRef, Component, NgZone, OnInit } from '@angular/core';
import { PrimengComponentsModule } from '../../shared/primeng-components-module';
import { CommonModule } from '@angular/common';
import { ElectronServicesCustom } from '../../service/electron-services-custom';

export interface ActivityEntry {
  id: string;
  type: 'search' | 'sync';
  timestamp: string;
  folder: string;
  query_image: string | null;
  duration_sec: number;
  result_count: number;
  indexed_count: number;
  error_count: number;
  results: { rank: number; path: string; similarity: number }[];
  errors: { file: string; reason: string }[];
  status: 'success' | 'partial' | 'error';
}

@Component({
  selector: 'app-activity-log',
  imports: [PrimengComponentsModule, CommonModule],
  templateUrl: './activity-log.html',
  styleUrl: './activity-log.scss',
})
export class ActivityLog implements OnInit {

  entries: ActivityEntry[] = [];
  filtered: ActivityEntry[] = [];
  loading = true;
  expanded = new Set<string>();
  typeFilter: 'all' | 'search' | 'sync' = 'all';

  constructor(
    private electronService: ElectronServicesCustom,
    private ngZone: NgZone,
    private cdr: ChangeDetectorRef
  ) { }

  ngOnInit() { this.load(); }

  async load() {
    this.loading = true;
    this.cdr.detectChanges();
    try {
      const data = await this.electronService.getActivityLog();
      this.ngZone.run(() => {
        this.entries = data;
        this.applyFilter();
        this.loading = false;
        this.cdr.detectChanges();
      });
    } catch (e) {
      console.error('Failed to load activity log', e);
      this.ngZone.run(() => { this.loading = false; this.cdr.detectChanges(); });
    }
  }

  applyFilter() {
    this.filtered = this.typeFilter === 'all'
      ? this.entries
      : this.entries.filter(e => e.type === this.typeFilter);
  }

  setFilter(f: 'all' | 'search' | 'sync') { this.typeFilter = f; this.applyFilter(); }
  toggleExpand(id: string) { this.expanded.has(id) ? this.expanded.delete(id) : this.expanded.add(id); }
  isExpanded(id: string) { return this.expanded.has(id); }

  fileName(path: string): string {
    return path ? path.replace(/\\/g, '/').split('/').pop() || path : '—';
  }
  shortPath(path: string): string {
    if (!path) return '—';
    const p = path.replace(/\\/g, '/').split('/');
    return p.length > 3 ? '…/' + p.slice(-2).join('/') : path;
  }
  formatDuration(sec: number): string {
    return sec < 60 ? `${sec.toFixed(1)}s` : `${Math.floor(sec / 60)}m ${Math.round(sec % 60)}s`;
  }
  statusSeverity(s: string): 'success' | 'warn' | 'danger' {
    return ({ success: 'success', partial: 'warn', error: 'danger' } as any)[s] ?? 'info';
  }

  get searchCount() { return this.entries.filter(e => e.type === 'search').length; }
  get syncCount() { return this.entries.filter(e => e.type === 'sync').length; }
  get errorCount() { return this.entries.filter(e => e.status !== 'success').length; }
}

