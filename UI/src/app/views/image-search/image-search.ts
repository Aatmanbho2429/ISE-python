import { ChangeDetectorRef, Component, NgZone, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PrimengComponentsModule } from '../../shared/primeng-components-module';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { ElectronServicesCustom } from '../../service/electron-services-custom';
import { shell } from 'electron';
import { SystemService } from '../../service/system-service';
import { TranslateModule } from '@ngx-translate/core';

@Component({
  selector: 'app-image-search',
  imports: [CommonModule, PrimengComponentsModule, FormsModule, ReactiveFormsModule, TranslateModule],
  templateUrl: './image-search.html',
  styleUrl: './image-search.scss',
})
export class ImageSearch implements OnInit {
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
  // public collection: any;

  constructor(public electronServiceCustom: ElectronServicesCustom, private ngZone: NgZone, private cdr: ChangeDetectorRef, public systemService: SystemService) {
    //this.electronServiceCustom.send();
    // this.performSearch();
    this.currentStep = 1;

    this.events = [
      "Select Search Image", "Choose Target Folder", "Search"
    ];
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
    // Step 1 validation
    if (step >= 2 && !this.queryString) {
      return false;
    }

    // Step 2 validation
    if (step >= 3 && !this.folderPath) {
      return false;
    }

    return true;
  }

  goToStep(step: number, current: number) {

    if (!this.validateStep(step)) {
      return;
    }

    this.currentStep = step;
  }

  fixPath(p: string): string {
    return "" + p.replace(/\\/g, "/");
  }

  async selectFolderPath() {
    let a = await this.electronServiceCustom.OpenFolderDialog();
    this.ngZone.run(() => {
      this.folderPath = a;
    });
    this.cdr.detectChanges();
  }

  async selectImagePath() {
    let a = await this.electronServiceCustom.OpenFileDialog();
    this.ngZone.run(() => {
      this.queryString = a;
      console.log(this.queryString)

    });
    this.cdr.detectChanges();
  }

  async addFolderToVectroDb() {
    if (this.folderPath !== '' && this.queryString !== '') {

      this.ngZone.run(() => {
        this.isSearching = true;
        this.results = [];
      });

      try {
        if (this.selectedResultNumber) {
          this.number_of_results = this.selectedResultNumber
        }
        const results = await this.electronServiceCustom.Search(
          this.queryString,
          this.folderPath,
          this.number_of_results
        );


        this.ngZone.run(() => {
          if (results && results.length > 0) {
            this.results = results.map((r: any) => ({
              path: this.fixPath(r.path),
              score: r.similarity
            }));

            this.systemService.showSuccess(
              `${results.length} similar images found. Scroll down to view results.`
            );
          } else {
            this.systemService.showWarning(
              'No similar images found for the given query.'
            );
          }
        });

      } catch (err: any) {

        let payload: any = null;

        try {
          const msg = err?.message || '';
          const jsonStart = msg.indexOf('{');

          if (jsonStart !== -1) {
            payload = JSON.parse(msg.substring(jsonStart));
          } else {
            throw new Error('No JSON payload');
          }
        } catch {
          payload = {
            error: 'Unknown error',
            details: err?.message || 'Search failed'
          };
        }

        this.ngZone.run(() => {

          if (payload.error?.toLowerCase().includes("license")) {
            this.displayMembershipPopup = true;

            this.systemService.showError(
              payload.details || payload.error
            );

            // if (payload.device_id) {
            //   this.systemService.showWarning(
            //     `Your Device ID: ${payload.device_id}`
            //   );
            // }

            return;
          }

          this.systemService.showError(
            payload.details || payload.error || "Search failed"
          );
        });
      } finally {
        this.ngZone.run(() => {
          this.isSearching = false;
          this.cdr.detectChanges();
        });
      }
    } else {
      this.systemService.showWarning(
        'Please select a folder and enter a search query.'
      );
    }
  }

  //   async addFolderToVectroDb() {
  //   if (this.folderPath !== '' && this.queryString !== '') {

  //     this.ngZone.run(() => {
  //       this.isSearching = true;
  //       this.results = [];
  //     });

  //     try {
  //       const results = await this.electronServiceCustom.Search(
  //         this.queryString,
  //         this.folderPath,
  //         this.number_of_results
  //       );
  //       console.log(results);

  //       this.ngZone.run(() => {
  //         this.results = results.map((r: any) => ({
  //           path: this.fixPath(r.path),
  //           score: r.similarity
  //         }));
  //         this.systemService.showSuccess("Similar images found. Please scoll down");
  //       });

  //     } catch (error) {
  //       console.error(error);
  //     } finally {
  //       this.ngZone.run(() => {
  //         this.isSearching = false;
  //         this.cdr.detectChanges();
  //       });
  //     }
  //   }
  // }



  // async OpenImgDialog(){
  //   await this.electronServiceCustom.OpenFileDialog();
  // }

}

interface SearchResult {
  // id:string,
  path: string;
  score: number;
}
