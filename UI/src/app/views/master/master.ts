import { ChangeDetectorRef, Component, NgZone, OnInit } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { MenuItem } from 'primeng/api';
import { PrimengComponentsModule } from '../../shared/primeng-components-module';
import { TranslateModule } from '@ngx-translate/core';
import { ElectronServicesCustom } from '../../service/electron-services-custom';
import { Subscription } from 'rxjs';
import { CommonModule } from '@angular/common';
import { verifyLicenseResponse } from '../../models/response/verifyLicenseResponse';


@Component({
  selector: 'app-master',
  imports: [RouterOutlet, PrimengComponentsModule, TranslateModule, CommonModule],
  templateUrl: './master.html',
  styleUrl: './master.scss',
})
export class Master implements OnInit {
  items: MenuItem[] | undefined;
  public subscriptions = new Subscription();

  // true = license INVALID = show blocking popup
  public isLicenseInvalid: boolean = false;
  public verifyLicenseResponse: verifyLicenseResponse = new verifyLicenseResponse();
  public deviceId: string = '';

  isSidebarCollapsed = false;

  menuItems: MenuItem[] = [
    { label: 'Dashboard', icon: 'pi pi-home', routerLink: '/image' },
    { label: 'Users', icon: 'pi pi-users', routerLink: '/users' },
    { label: 'Settings', icon: 'pi pi-cog', routerLink: '/' }
  ];

  constructor(
    public electronServiceCustom: ElectronServicesCustom,
    private ngZone: NgZone,
    private cdr: ChangeDetectorRef
  ) { }

  async ngOnInit() {
    setTimeout(() => {
      this.validateLicense();
    }, 1000);
  }

  async validateLicense() {
    try {
      const raw = await this.electronServiceCustom.validateLicense();
      const response = typeof raw === 'string' ? JSON.parse(raw) : raw;

      this.verifyLicenseResponse.status = response.status;
      this.verifyLicenseResponse.message = response.message;
      this.verifyLicenseResponse.code = response.code;

      // Show blocking popup if license is NOT valid
      this.isLicenseInvalid = !response.status;

      // If invalid — also fetch device ID so user can send it to you
      if (this.isLicenseInvalid) {
        try {
          this.deviceId = await this.electronServiceCustom.getDeviceId();
        } catch {
          this.deviceId = 'Unable to retrieve device ID';
        }
      }

    } catch {
      this.isLicenseInvalid = true;
      this.verifyLicenseResponse.message = 'License validation failed. Please contact support.';
    }

    this.cdr.markForCheck();
  }

  toggleSidebar() {
    this.isSidebarCollapsed = !this.isSidebarCollapsed;
  }
  copyDeviceId() {
    navigator.clipboard.writeText(this.deviceId);
  }
}

// Add this method inside the Master class:
