import { Component, OnInit, OnDestroy, NgZone, ChangeDetectorRef } from '@angular/core';
import { PrimengComponentsModule } from '../../shared/primeng-components-module';
import { CommonModule } from '@angular/common';
import {
  FlatDirectory,
  flattenTree,
  groupByDirectory,
  GroupedFileTree,
  PrimeTreeNode,
  toPrimeNgTreeNodes,
  RawFileIndex,
} from '../../service/group-files-by-directory';
import { HttpClient } from '@angular/common/http';
import { interval, Subscription, switchMap, distinctUntilChanged, map } from 'rxjs';
import { ElectronServicesCustom } from '../../service/electron-services-custom';
import { SystemService } from '../../service/system-service';

@Component({
  selector: 'app-loaded-folder',
  imports: [PrimengComponentsModule, CommonModule],
  templateUrl: './loaded-folder.html',
  styleUrl: './loaded-folder.scss',
})
export class LoadedFolder implements OnInit {

  tree!: GroupedFileTree;
  primeNodes: PrimeTreeNode[] = [];
  flatDirs: FlatDirectory[] = [];
  searchResults: any[] = [];
  isSearching = false;

  private pollSub?: Subscription;
  private lastNextId: number = -1;
  private readonly META_URL = '../../../../../faiss/meta.json';
  private readonly POLL_INTERVAL = 2000;

  constructor(private http: HttpClient, public electronServiceCustom: ElectronServicesCustom, private ngZone: NgZone, private cdr: ChangeDetectorRef, public systemService: SystemService) { }

  ngOnInit(): void {
    setTimeout(() => {
      //this.displayFolder();
    }, 1000);
  }

  async displayFolder() {
    let result=await this.electronServiceCustom.getLoadedData();
    console.log('Raw folder tree:', result);
  }
}