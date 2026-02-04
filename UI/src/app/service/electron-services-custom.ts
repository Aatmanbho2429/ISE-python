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
      console.log('Result from Python:', result);
      returnValue = result;
    });
    return returnValue;
  }

  OpenFolderDialog() {
    let returnValue;
    if (this.electron.isElectronApp) {
      // console.log("Send search request");
      returnValue = this.electron.ipcRenderer.invoke('select-folder');
    } else {
      console.warn("Not running inside Electron.");
    }
    return returnValue;
  }

  OpenFileDialog() {
    let returnValue;
    window.pywebview.api.selectFile().then((result: string) => {
      console.log('Result from Python:', result);
      returnValue = result;
    });
    return returnValue;
  }
}

declare global {
  interface Window {
    pywebview: any;
  }
}
