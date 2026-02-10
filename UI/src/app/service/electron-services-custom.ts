import { Injectable } from '@angular/core';
import { ElectronService } from 'ngx-electron';

@Injectable({
  providedIn: 'root',
})
export class ElectronServicesCustom {

  constructor(public electron: ElectronService) {

  }

  async Search(query_string: string, folder_path: string, number_of_results: number) {
    let result=await window.pywebview.api.start_search(query_string, folder_path, number_of_results);
    return result;
  }

  async OpenFolderDialog() :Promise<string>{
    let result=await window.pywebview.api.selectFolder();
    return result;
  }

  async OpenFileDialog():Promise<string> {
    let result=await window.pywebview.api.selectFile();
    return result;
  }

  async ValidateLicense():Promise<any> {
    let result=await window.pywebview.api.validateLicense();
    return result;
  }
}

declare global {
  interface Window {
    pywebview: any;
  }
}
