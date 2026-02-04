import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { ElectronService } from 'ngx-electron';
import { routes } from './app.routes';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { providePrimeNG } from 'primeng/config';
import Aura from '@primeuix/themes/aura';
import { provideHttpClient } from '@angular/common/http';
import { JWT_OPTIONS, JwtHelperService } from '@auth0/angular-jwt';
import { MessageService } from 'primeng/api';
import { DatePipe } from '@angular/common';
import { provideTranslateService } from '@ngx-translate/core';
import { provideTranslateHttpLoader, TranslateHttpLoader } from '@ngx-translate/http-loader';


export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideAnimationsAsync(),
    provideHttpClient(),
    providePrimeNG({
      theme: {
        preset: Aura,
        options: {
          darkModeSelector: '' // disable dark mode
        }
      }
    }),
    ElectronService,
    { provide: JWT_OPTIONS, useValue: JWT_OPTIONS },JwtHelperService,
    MessageService,
    DatePipe,
    provideTranslateService({
      loader: provideTranslateHttpLoader({ prefix: "./assets/i18n/" }),
      fallbackLang: 'en',
      lang: 'en'
    })
  ]
};
