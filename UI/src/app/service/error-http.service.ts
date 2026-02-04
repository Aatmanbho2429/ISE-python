import { Injectable } from '@angular/core';
import { AppInsightsService } from './app-insights.service';
import { HttpEvent, HttpHandler, HttpInterceptor, HttpRequest } from '@angular/common/http';
import { Cookie } from './cookie';
import { SystemService } from './system-service';
import { catchError, Observable, throwError } from 'rxjs';
import { JwtHelperService } from '@auth0/angular-jwt';
import { CookieConstant } from '../models/const/cookieConstant';


@Injectable({
  providedIn: 'root',
})
export class ErrorHttpService implements HttpInterceptor{
  insightService: AppInsightsService;
    constructor(public system: SystemService, private cookie: Cookie, private jwtHelper: JwtHelperService, appInsightsService: AppInsightsService) {
        this.insightService = appInsightsService;
    }

    intercept(request: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
        // let token = this.cookie.GetCookie(CookieConstant.cal_Token);
        // let token = localStorage.getItem('jwtToken')
        let token = this.cookie.GetCookie(CookieConstant.Web_Token)
        return next.handle(request).pipe(catchError(err => {
            this.insightService.logException(err.error);
            if ([401, 403].includes(err.status) && this.jwtHelper.isTokenExpired(token)) {
                window.location.reload();
            } else {
                // auto logout if 401 or 403 response returned from api
                // this.system.logout();
            }
            const error = err.error?.message || err.statusText;
            //console.error(err);
            return throwError(() => error);
        }));
    }
}
