import { Component, OnInit } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { MenuItem } from 'primeng/api';
import { PrimengComponentsModule } from '../../shared/primeng-components-module';
import { TranslateModule } from '@ngx-translate/core';

@Component({
  selector: 'app-master',
  imports: [RouterOutlet, PrimengComponentsModule,TranslateModule],
  templateUrl: './master.html',
  styleUrl: './master.scss',
})
export class Master implements OnInit {
  items: MenuItem[] | undefined;
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
            routerLink:'/image'
          },
          {
            label: 'Search',
            icon: 'pi pi-search',
            routerLink:''

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
}
