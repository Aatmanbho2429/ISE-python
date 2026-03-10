import { ChangeDetectorRef, Component, NgZone, OnInit, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PrimengComponentsModule } from '../../shared/primeng-components-module';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { ElectronServicesCustom } from '../../service/electron-services-custom';
import { SystemService } from '../../service/system-service';
import { TranslateModule } from '@ngx-translate/core';
import { ProgressBarComponent } from '../progress-bar/progress-bar';

@Component({
  selector: 'app-image-search',
  imports: [
    CommonModule,
    PrimengComponentsModule,
    FormsModule,
    ReactiveFormsModule,
    TranslateModule,
    ProgressBarComponent   // ← ADD THIS
  ],
  templateUrl: './image-search.html',
  styleUrl: './image-search.scss',
})
export class ImageSearch implements OnInit {

  @ViewChild(ProgressBarComponent) progressBar!: ProgressBarComponent;  // ← ADD THIS

  public results: SearchResult[] = [];
  public queryString: string = "";
  public folderPath: string = "";
  public number_of_results: number = 30;
  events: string[];
  public currentStep: number = 1;
  public subscriptions = new Subscription();
  public isSearching: boolean = false;
  public displayMembershipPopup: boolean = false;
  numberOFResults: any[] | undefined;
  selectedResultNumber: any | undefined;

  constructor(
    public electronServiceCustom: ElectronServicesCustom,
    private ngZone: NgZone,
    private cdr: ChangeDetectorRef,
    public systemService: SystemService
  ) {
    this.currentStep = 1;
    this.events = ["Select Search Image", "Choose Target Folder", "Search"];
  }

  ngOnInit(): void {
    this.numberOFResults = [
      { name: '10', code: 10 },
      { name: '20', code: 20 },
      { name: '30', code: 30 },
      { name: '50', code: 50 }
    ];
    if (!this.validateStep(this.currentStep)) {
      this.currentStep = 1;
    }
  }

  validateStep(step: number): boolean {
    if (step >= 2 && !this.queryString) return false;
    if (step >= 3 && !this.folderPath) return false;
    return true;
  }

  goToStep(step: number, current: number) {
    if (!this.validateStep(step)) return;
    this.currentStep = step;
  }

  fixPath(p: string): string {
    return "" + p.replace('file:///', '');
  }

  async selectFolderPath() {
    let a = await this.electronServiceCustom.OpenFolderDialog();
    this.ngZone.run(() => { this.folderPath = a; });
    this.cdr.detectChanges();
  }

  async selectImagePath() {
    let a = await this.electronServiceCustom.OpenFileDialog();
    this.ngZone.run(() => { this.queryString = this.fixPath(a); });
    this.cdr.detectChanges();
  }

  async addFolderToVectroDb() {
    if (!this.folderPath || !this.queryString) {
      this.systemService.showWarning('Please select a folder and enter a search query.');
      return;
    }

    this.ngZone.run(() => {
      this.isSearching = true;
      this.results = [];
    });

    // ── START PROGRESS BAR ───────────────────────────────────────────────
    this.progressBar?.startPolling();
    // ────────────────────────────────────────────────────────────────────

    try {
      if (this.selectedResultNumber) {
        this.number_of_results = this.selectedResultNumber;
      }

      const response = await this.electronServiceCustom.Search(
        this.queryString,
        this.folderPath,
        this.number_of_results
      );
      // console.log("Raw response from Search:", response);
      const parsed = typeof response === 'string' ? JSON.parse(response) : response;

      this.ngZone.run(async () => {
        if (!parsed.status) {
          this.systemService.showError(parsed.message || "Search failed");
          return;
        }
        // console.log("parsed variable:", parsed);
        const resultsArray = parsed.data?.results || [];

        if (resultsArray.length > 0) {
          this.results = resultsArray.map((r: any) => ({
            path: this.fixPath(r.path),
            score: r.similarity
          }));
          this.loadThumbnails();
          this.systemService.showSuccess(`${resultsArray.length} similar images found.`);
        } else {
          this.results = [];
          this.systemService.showWarning('No similar images found for the given query.');
        }
      });

    } catch (err: any) {
      let message = err?.message || "An error occurred during the search.";
      this.systemService.showError(message);
      // let payload: any = null;
      // try {
      //   const msg       = err?.message || '';
      //   const jsonStart = msg.indexOf('{');
      //   payload = jsonStart !== -1
      //     ? JSON.parse(msg.substring(jsonStart))
      //     : { error: 'Unknown error', details: err?.message || 'Search failed' };
      // } catch {
      //   payload = { error: 'Unknown error', details: err?.message || 'Search failed' };
      // }

      // this.ngZone.run(() => {
      //   if (payload.error?.toLowerCase().includes("license")) {
      //     this.displayMembershipPopup = true;
      //     this.systemService.showError(payload.details || payload.error);
      //     return;
      //   }
      //   this.systemService.showError(payload.details || payload.error || "Search failed");
      // });

    } finally {
      // ── STOP PROGRESS BAR ──────────────────────────────────────────────
      setTimeout(() => this.progressBar?.stopPolling(), 1000); // 1s delay so "Done" is visible
      // ──────────────────────────────────────────────────────────────────
      this.ngZone.run(() => {
        this.isSearching = false;
        this.cdr.detectChanges();
      });
    }
  }

  async openFilePath(path: string) {
    await this.electronServiceCustom.OpenFilePath(path);
  }

  async loadThumbnails() {
    for (const item of this.results) {
      item.thumbnail = '';          // show spinner while loading
      item.thumbnail = await this.electronServiceCustom.getThumbnail(item.path);
    }
  }
}

interface SearchResult {
  path: string;
  score: number;
  thumbnail?: string;
}