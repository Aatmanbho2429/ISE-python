import { Injectable } from '@angular/core';
import { ElectronService } from 'ngx-electron';

@Injectable({
  providedIn: 'root',
})
export class ElectronServicesCustom {

  constructor(public electron: ElectronService) {

  }

  Search(query_string: string, folder_path: string, number_of_results: number) {
    let returnValue;
    window.pywebview.api.add(5, 3).then((result: number) => {
      returnValue = result;
    });
    return returnValue;
  }

  async OpenFolderDialog() :Promise<string>{
    let result=await window.pywebview.api.selectFolder();
    return result;
  }

  async OpenFileDialog():Promise<string> {
    let result=await window.pywebview.api.selectFile();
    return result;
  }
}

declare global {
  interface Window {
    pywebview: any;
  }
}
