import { Inject, Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { Cookie } from './cookie';
import { CookieService } from 'ngx-cookie-service';
import { AppInsightsService } from './app-insights.service';
import { CookieConstant } from '../models/const/cookieConstant';
import { BaseResponse } from '../models/response/baseResponse';

@Injectable({
    providedIn: 'root',
})

export abstract class CoreDataService {
    private url: string = '';
    private endpoint: string = '';
    companyId: string = '';
    insightService: AppInsightsService;
    constructor(
        private httpClient: HttpClient,
        @Inject(String) url: string,
        @Inject(String) endpoint: string,
        public cookie: Cookie,
        appInsightsService: AppInsightsService
    ) {
        this.url = url;
        this.endpoint = endpoint;
        this.insightService = appInsightsService;
    }

    private getHeader(): HttpHeaders {
        const headerss = new HttpHeaders({
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': 'false',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,PUT,POST,DELETE',
            //Authorization: `Bearer ${localStorage.getItem('jwtToken')}`,
            Authorization: `Bearer ${this.cookie.GetCookie(CookieConstant.Web_Token)}`,
            // Authorization: `Bearer sdf`,
            // 'CompanyId': this.cookie.GetCookie(CookieConstant.cal_SelectedLanguage) == "1" ? '' : this.cookie.GetCookie(CookieConstant.cal_SelectedLanguage)
        });

        return headerss;
    }

    put<RS,T>(
        id: string | number,
        action: string,
        resource: T
    ): Observable<BaseResponse<RS>> {
        return this.httpClient
            .put<BaseResponse<RS>>(
                `${this.url}/${this.endpoint}` + (action != '' ? `/${action}` : '') + (id != 0 ? `/${id}` : ''),
                JSON.stringify(resource),
                {
                    headers: this.getHeader(),
                }
            )
            .pipe(
                map((list) => list),
                catchError(this.handleError)
            );
    }
    post<T, RS>(resource: T, action: string): Observable<BaseResponse<RS>> {
        return this.httpClient
            .post<BaseResponse<RS>>(
                `${this.url}/${this.endpoint}/${action}`,
                JSON.stringify(resource),
                {
                    headers: this.getHeader(),
                }
            )
            .pipe(
                map((list) => list),
                catchError(this.handleError)
            );
    }

    get<RS>(id: string | number, action: string): Observable<BaseResponse<RS>> {
        return this.httpClient
            .get<BaseResponse<RS>>(`${this.url}/${this.endpoint}` + (action != '' ? `/${action}` : '') + `/${id}`, {
                headers: this.getHeader(),
            })
            .pipe(
                map((list) => list),
                catchError(this.handleError)

            );

    }
    login<T, RS>(resource: T, action: string): Observable<BaseResponse<RS>> {
        return this.httpClient
            .post<BaseResponse<RS>>(
                `${this.url}/${this.endpoint}/${action}`,
                JSON.stringify(resource),
                {
                    headers: this.getHeader(),
                }
            )
            .pipe(
                map((list) => list),
                catchError(this.handleError)
            );
    }
    getUI<RS>(id: string | number, action: string): Observable<BaseResponse<RS>> {
        return this.httpClient
            .get<BaseResponse<RS>>(`${this.url}/${this.endpoint}` + (action != '' ? `/${action}` : '') + `/${id}`, {
                headers: this.getHeader(),
            })
            .pipe(
                map((list) => list),
                catchError(this.handleError)

            );

    }

    list<RS>(queryString: object, action: string): Observable<BaseResponse<RS>> {
        return this.httpClient
            .get<BaseResponse<RS>>(
                `${this.url}/${this.endpoint}${action}` + (Object.keys(queryString).length > 0 ? `?${this.toQueryParams(queryString)}` : ''),
                {
                    headers: this.getHeader(),
                }
            )
            .pipe(
                map((list) => list),
                catchError(this.handleError)
            );
    }

    delete<RS>(
        id: string | number,
        action: string
    ): Observable<BaseResponse<RS>> {
        return this.httpClient
            .delete<BaseResponse<RS>>(
                `${this.url}/${this.endpoint}` + (action != '' ? `/${action}` : '') + `/${id}`,
                {
                    headers: this.getHeader(),
                }
            )
            .pipe(
                map((list) => list),
                catchError(this.handleError)
            );
    }

    postForm(resource, action: string) {
        let headers = new HttpHeaders().set('Authorization', `Bearer ${this.cookie.GetCookie(CookieConstant.Web_Token)}`);
        return this.httpClient.post(`${this.url}/${this.endpoint}/${action}`, resource, { headers })
            .pipe(map((list) => list), catchError(this.handleError));
    }

    private handleError(error: any) {
        // Handle the HTTP error here

        if (error.status == 500) {
            if (
                JSON.parse(error._body).ExceptionMessage ==
                'authorization token expired' ||
                JSON.parse(error._body).ExceptionMessage ==
                'authorization token is missing' ||
                JSON.parse(error._body).ExceptionMessage ==
                'invalid authorization token'
            ) {
                //this.adalService.login();
                // Over Here Call Login Page
            } else {
                // this.insightService.logException(error);
                console.log(error);
            }
        } else {
            // this.insightService.logException(error);
            console.log(error);
        }
        return throwError('Something wrong happened');
    }
    toQueryParams(data: Record<string, any>) {
        return Object.entries(data)
            .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
            .join("&");
    }
}
