import { ChangeDetectorRef, Component, NgZone, OnInit } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { MenuItem } from 'primeng/api';
import { PrimengComponentsModule } from '../../shared/primeng-components-module';
import { TranslateModule } from '@ngx-translate/core';
import { ElectronServicesCustom } from '../../service/electron-services-custom';
import { Subscription } from 'rxjs';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';                  // ← NEW
import { verifyLicenseResponse } from '../../models/response/verifyLicenseResponse';


@Component({
  selector: 'app-master',
  imports: [RouterOutlet, PrimengComponentsModule, TranslateModule, CommonModule, FormsModule], // ← added FormsModule
  templateUrl: './master.html',
  styleUrl: './master.scss',
})
export class Master implements OnInit {
  items: MenuItem[] | undefined;
  public subscriptions = new Subscription();

  // ── CHANGED — renamed to isLoginRequired (was isLicenseInvalid) ─────
  public isLoginRequired: boolean = false;
  public verifyLicenseResponse: verifyLicenseResponse = new verifyLicenseResponse();
  public deviceId: string = '';

  // ── NEW — login form fields ──────────────────────────────────────────
  public loginEmail:    string  = '';
  public loginPassword: string  = '';
  public loginLoading:  boolean = false;
  public loginError:    string  = '';

  isSidebarCollapsed = false;

  menuItems: MenuItem[] = [
    { label: 'Dashboard', icon: 'pi pi-home',  routerLink: '/image' },
    { label: 'Users',     icon: 'pi pi-users', routerLink: '/users' },
    { label: 'Settings',  icon: 'pi pi-cog',   routerLink: '/'      }
  ];

  constructor(
    public electronServiceCustom: ElectronServicesCustom,
    private ngZone: NgZone,
    private cdr: ChangeDetectorRef
  ) { }

  async ngOnInit() {
    setTimeout(() => {
      this.validateLogin();         // ← CHANGED from validateLicense()
    }, 1000);
  }

  // ── CHANGED — was validateLicense(), now checks saved JWT token ──────
  async validateLogin() {
    try {
      const raw      = await this.electronServiceCustom.validateLogin();
      const response = typeof raw === 'string' ? JSON.parse(raw) : raw;

      if (response.success) {
        // Token valid — user is logged in, show main app
        this.isLoginRequired = false;
        this.verifyLicenseResponse.success    = true;
        this.verifyLicenseResponse.first_name = response.user?.first_name || '';
        this.verifyLicenseResponse.email      = response.user?.email || '';
      } else {
        // No token or expired — show login screen
        this.isLoginRequired = true;
        this.loginError      = '';
      }

    } catch {
      this.isLoginRequired = true;
      this.loginError      = 'Connection error. Please try again.';
    }

    this.cdr.markForCheck();
  }

  // ── NEW — called when designer clicks Login button ───────────────────
  async submitLogin() {
    if (!this.loginEmail || !this.loginPassword) {
      this.loginError = 'Please enter your email and password.';
      return;
    }

    this.loginLoading = true;
    this.loginError   = '';

    try {
      const raw      = await this.electronServiceCustom.login(this.loginEmail, this.loginPassword);
      const response = typeof raw === 'string' ? JSON.parse(raw) : raw;

      if (response.success) {
        // Login successful — hide login screen, show main app
        this.isLoginRequired = false;
        this.verifyLicenseResponse.success    = true;
        this.verifyLicenseResponse.first_name = response.user?.first_name || '';
        this.verifyLicenseResponse.email      = response.user?.email || '';
        this.loginPassword = '';   // clear password from memory
      } else {
        this.loginError = response.message || 'Login failed. Please try again.';
      }

    } catch {
      this.loginError = 'Connection error. Please try again.';
    }

    this.loginLoading = false;
    this.cdr.markForCheck();
  }

  // ── NEW — called from logout button ─────────────────────────────────
  async logout() {
    await this.electronServiceCustom.logout();
    this.isLoginRequired = true;
    this.loginEmail      = '';
    this.loginPassword   = '';
    this.loginError      = '';
    this.cdr.markForCheck();
  }

  // ── NEW — request device reset ───────────────────────────────────────
  async requestDeviceReset() {
    if (!this.loginEmail) {
      this.loginError = 'Please enter your email first.';
      return;
    }
    try {
      const raw    = await this.electronServiceCustom.requestDeviceReset(
        this.loginEmail, 'User requested device reset'
      );
      const result = typeof raw === 'string' ? JSON.parse(raw) : raw;
      this.loginError = result.message || 'Reset request sent. Contact support.';
    } catch {
      this.loginError = 'Could not send reset request.';
    }
    this.cdr.markForCheck();
  }

  // ── Kept exactly the same ────────────────────────────────────────────
  toggleSidebar() {
    this.isSidebarCollapsed = !this.isSidebarCollapsed;
  }

  copyDeviceId() {
    navigator.clipboard.writeText(this.deviceId);
  }
}