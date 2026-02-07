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
  licenseValidateResponse: any;
  public subscriptions = new Subscription();
  public isLicenseValid: boolean = false;

  public verifyLicenseResponse: verifyLicenseResponse = new verifyLicenseResponse();

  constructor(public electronServiceCustom: ElectronServicesCustom, private ngZone: NgZone, private cdr: ChangeDetectorRef) {

  }

  ngOnInit() {
    this.items = [
      {
        separator: true
      },
      {
        label: 'Documents',
        items: [
          {
            label: 'New',
            icon: 'pi pi-plus',
            routerLink: '/image'
          },
          {
            label: 'Search',
            icon: 'pi pi-search',
            routerLink: ''

          }
        ]
      },
      {
        label: 'Profile',
        items: [
          {
            label: 'Settings',
            icon: 'pi pi-cog',
            shortcut: '⌘+O'
          },
          {
            label: 'Messages',
            icon: 'pi pi-inbox',
            badge: '2'
          },
          {
            label: 'Logout',
            icon: 'pi pi-sign-out',
            shortcut: '⌘+Q',
            linkClass: '!text-red-500 dark:!text-red-400'
          }
        ]
      },
      {
        separator: true
      }
    ];

    setTimeout(() => {
      this.validateLicense();
    }, 1000);
  }
  isSidebarCollapsed = false;

  menuItems: MenuItem[] = [
    {
      label: 'Dashboard',
      icon: 'pi pi-home',
      routerLink: '/image',
      items: []
    },
    {
      label: 'Users',
      icon: 'pi pi-users',
      routerLink: '/users'
    },
    {
      label: 'Settings',
      icon: 'pi pi-cog',
      routerLink: '/'
    }
  ];

  toggleSidebar() {
    this.isSidebarCollapsed = !this.isSidebarCollapsed;
  }

  async validateLicense() {
    this.licenseValidateResponse = await this.electronServiceCustom.ValidateLicense();
    this.licenseValidateResponse = JSON.parse(this.licenseValidateResponse)
    // console.log('Parsed license validation response: ', a);
    this.verifyLicenseResponse.status = this.licenseValidateResponse.status;
    this.verifyLicenseResponse.message = this.licenseValidateResponse.message;
    this.verifyLicenseResponse.code = this.licenseValidateResponse.code;
    this.ngZone.run(() => {
      this.isLicenseValid = !this.verifyLicenseResponse.status;
      this.cdr.detectChanges();
    });
    console.log('licenseValidateResponse: ', this.licenseValidateResponse);
    console.log('License validation response: ', this.verifyLicenseResponse);
  }
}
