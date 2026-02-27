import {
  Component, OnInit, OnDestroy,
  ChangeDetectionStrategy, ChangeDetectorRef
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ElectronServicesCustom } from '../../service/electron-services-custom'; // adjust path if needed

@Component({
  selector: 'app-progress-bar',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './progress-bar.html',
  styleUrl: './progress-bar.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProgressBarComponent implements OnInit, OnDestroy {

  progress = {
    active:  false,
    total:   0,
    done:    0,
    current: '',
    percent: 0,
    phase:   'idle',
    errors:  0
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
        // Keep "Done" visible 1.5s then hide and auto-stop
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