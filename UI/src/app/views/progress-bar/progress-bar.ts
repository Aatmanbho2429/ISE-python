import {
  Component, OnInit, OnDestroy,
  ChangeDetectionStrategy, ChangeDetectorRef
} from '@angular/core';
import { CommonModule, KeyValuePipe } from '@angular/common';
import { ElectronServicesCustom } from '../../service/electron-services-custom';

@Component({
  selector: 'app-progress-bar',
  standalone: true,
  imports: [CommonModule, KeyValuePipe],
  templateUrl: './progress-bar.html',
  styleUrl: './progress-bar.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProgressBarComponent implements OnInit, OnDestroy {

  progress: any = {
    active:     false,
    total:      0,
    done:       0,
    current:    '',
    percent:    0,
    phase:      'idle',
    errors:     0,
    eta_sec:    -1,
    elapsed:    0,
    file_types: {}
  };

  get visible(): boolean {
    return this.progress.active || this.progress.percent > 0;
  }

  get phaseLabel(): string {
    switch (this.progress.phase) {
      case 'hashing':   return '🔍 Scanning files...';
      case 'embedding': return '⚡ Indexing images...';
      case 'searching': return '🔎 Searching...';
      default:          return this.progress.percent >= 100 ? '✅ Done' : '';
    }
  }

  get fileTypeList(): { ext: string; done: number; total: number }[] {
    const ft = this.progress.file_types || {};
    return Object.entries(ft).map(([ext, val]: [string, any]) => ({
      ext: ext.toUpperCase(),
      done: val.done,
      total: val.total
    }));
  }

  formatTime(seconds: number): string {
    if (seconds <= 0) return '0s';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
  }

  get etaLabel(): string {
    if (!this.progress.active)       return '';
    if (this.progress.eta_sec < 0)   return 'Estimating...';
    if (this.progress.eta_sec === 0) return 'Almost done';
    return `~${this.formatTime(this.progress.eta_sec)} remaining`;
  }

  get elapsedLabel(): string {
    if (this.progress.elapsed <= 0) return '';
    return `${this.formatTime(Math.floor(this.progress.elapsed))} elapsed`;
  }

  private pollInterval: any;

  constructor(
    private electronService: ElectronServicesCustom,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit() {}

  startPolling() {
    if (this.pollInterval) return;
    this.progress = { ...this.progress, percent: 0, done: 0, active: true };
    this.cdr.markForCheck();
    this.pollInterval = setInterval(() => this.poll(), 500);
  }

  stopPolling() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  }

  private async poll() {
    try {
      const data = await this.electronService.getProgress();
      this.progress = data;
      this.cdr.markForCheck();
      if (!data.active && data.percent >= 100) {
        setTimeout(() => {
          this.progress = { ...this.progress, percent: 0, active: false };
          this.cdr.markForCheck();
          this.stopPolling();
        }, 1500);
      }
    } catch {
      // pywebview not ready yet — ignore
    }
  }

  ngOnDestroy() {
    this.stopPolling();
  }
}