import { Injectable } from '@angular/core';
import { ElectronService } from 'ngx-electron';
import { FolderStatusResponse } from '../models/response/folderStatusResponse';

@Injectable({
  providedIn: 'root',
})
export class ElectronServicesCustom {

  constructor(public electron: ElectronService) {

  }

  async Search(query_string: string, folder_path: string, number_of_results: number) {
    let result = await window.pywebview.api.start_search(query_string, folder_path, number_of_results);
    return result;
  }

  async OpenFolderDialog(): Promise<string> {
    let result = await window.pywebview.api.selectFolder();
    return result;
  }

  async OpenFileDialog(): Promise<string> {
    let result = await window.pywebview.api.selectFile();
    return result;
  }

  async ValidateLicense(): Promise<any> {
    let result = await window.pywebview.api.validateLicense();
    return result;
  }

  async OpenFilePath(path: string): Promise<any> {
    await window.pywebview.api.openFilePath(path);
  }

  async getFolderTree(): Promise<any> {
    let result = 2//await window.pywebview.api.getFolderTree();
    return result;
  }

  async getProgress(): Promise<any> {
    const raw = await window.pywebview.api.get_progress();
    return typeof raw === 'string' ? JSON.parse(raw) : raw;
  }

  async getFolderStatuses(): Promise<FolderStatusResponse> {
    const raw = await window.pywebview.api.get_folder_statuses();
    return typeof raw === 'string' ? JSON.parse(raw) : raw;
  }

  async syncFolder(folder_path: string): Promise<any> {
    const raw = await window.pywebview.api.sync_folder(folder_path);
    return typeof raw === 'string' ? JSON.parse(raw) : raw;
  }

  async getThumbnail(path: string): Promise<string> {
    const result = await window.pywebview.api.get_thumbnail(path);
    return result;
    return (window as any).pywebview.api.get_thumbnail(path);
  }

  getDeviceId(): Promise<string> {
    return (window as any).pywebview.api.getDeviceId();
  }

  validateLicense(): Promise<string> {
    return (window as any).pywebview.api.validateLicense();
  }

  async getActivityLog(): Promise<any[]> {
    const raw = await (window as any).pywebview.api.get_activity_log();
    return typeof raw === 'string' ? JSON.parse(raw) : raw;
  }
}

declare global {
  interface Window {
    pywebview: any;
  }
}
