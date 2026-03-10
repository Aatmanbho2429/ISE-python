import { ChangeDetectorRef, Component, NgZone, OnInit, ViewChild } from '@angular/core';
import { PrimengComponentsModule } from '../../shared/primeng-components-module';
import { CommonModule } from '@angular/common';
import { FileNodeData, FileStatusType, FolderStatusResponse, FolderStatusType, FolderSummary, TreeNode } from '../../models/response/folderStatusResponse';
import { ElectronServicesCustom } from '../../service/electron-services-custom';
import { SystemService } from '../../service/system-service';
import { ProgressBarComponent } from '../progress-bar/progress-bar';
import { TranslateModule } from '@ngx-translate/core';

@Component({
    selector: 'app-folder-status',
    imports: [PrimengComponentsModule, CommonModule, ProgressBarComponent, TranslateModule],
    templateUrl: './folder-status.html',
    styleUrl: './folder-status.scss',
})
export class FolderStatus implements OnInit {

    @ViewChild(ProgressBarComponent) progressBar!: ProgressBarComponent;

    tree: TreeNode[] = [];
    flat_list: FolderSummary[] = [];
    loading: boolean = true;
    loadingFolder: string | null = null;

    constructor(
        private electronService: ElectronServicesCustom,
        private cdr: ChangeDetectorRef,
        private ngZone: NgZone,
        private systemService: SystemService
    ) { }

    ngOnInit() {
        setTimeout(() => this.load(), 1000);
    }

    async load() {
        this.ngZone.run(() => {
            this.loading = true;
            this.cdr.detectChanges();
        });
        try {
            const data: FolderStatusResponse = await this.electronService.getFolderStatuses();
            // console.log(data)
            this.ngZone.run(() => {
                this.tree = data.tree;
                this.flat_list = data.flat_list;
                this.loading = false;
                this.cdr.detectChanges();
            });
        } catch (e) {
            console.error('Failed to load folder statuses', e);
            this.ngZone.run(() => {
                this.loading = false;
                this.cdr.detectChanges();
            });
        }
    }

    async LoadAFolder() {
        const result = await this.electronService.OpenFolderDialog();
        // console.log('Selected folder:', result);
        if (result) {
            await this.loadFolder(result);

        }
    }

    async loadFolder(folderPath: string) {
        this.ngZone.run(() => {
            this.loadingFolder = folderPath;
            this.cdr.detectChanges();
        });

        this.progressBar?.startPolling();

        try {
            const response = await this.electronService.syncFolder(folderPath);
            const parsed = typeof response === 'string' ? JSON.parse(response) : response;

            if (parsed.status) {
                this.systemService.showSuccess('Folder loaded successfully');
            } else {
                this.systemService.showError(parsed.message || 'Load failed');
            }
        } catch (e: any) {
            this.systemService.showError(e?.message || 'Load failed');
        } finally {
            setTimeout(() => this.progressBar?.stopPolling(), 1000);
            this.ngZone.run(() => {
                this.loadingFolder = null;
                this.cdr.detectChanges();
            });
            await this.load();
        }
    }

    isFolderNode(node: TreeNode): boolean {
        return !node.leaf;
    }

    asFolderData(node: TreeNode): FolderSummary {
        return node.data as FolderSummary;
    }

    asFileData(node: TreeNode): FileNodeData {
        return node.data as FileNodeData;
    }

    folderSeverity(status: FolderStatusType): 'success' | 'warn' | 'danger' {
        switch (status) {
            case 'fully_loaded': return 'success';
            case 'partial': return 'warn';
            case 'folder_missing': return 'danger';
        }
    }

    folderLabel(status: FolderStatusType): string {
        switch (status) {
            case 'fully_loaded': return 'Fully Loaded';
            case 'partial': return 'Partial';
            case 'folder_missing': return 'Folder Missing';
        }
    }

    fileSeverity(status: FileStatusType): 'success' | 'warn' {
        return status === 'loaded' ? 'success' : 'warn';
    }

    fileLabel(status: FileStatusType): string {
        return status === 'loaded' ? 'Indexed' : 'Not Indexed';
    }

}
