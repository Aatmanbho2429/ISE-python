import { Injectable } from '@angular/core';
import { Subscription } from 'rxjs';
import { TranslateService } from '@ngx-translate/core';
import { MessageService } from 'primeng/api';
import { Router } from '@angular/router';
import { Cookie } from './cookie';
import { HttpClient } from '@angular/common/http';
import { DatePipe } from '@angular/common';
import { NotificationType } from '../models/const/constants';
import { menuItem } from '../models/response/menuItemListResponse';

@Injectable({
    providedIn: 'root',
})
export class SystemService {
    public stateStorage: string = "cookie";
    public notificationType = new NotificationType();
    public subscriptions = new Subscription();

    constructor(public Translator: TranslateService, private messageService: MessageService,
        private http: HttpClient, private cookie: Cookie, private router: Router, private datePipe: DatePipe) { }

    getMenuItem() {
        return this.http.get<any>('assets/menu.json').toPromise().then(res => <menuItem[]>res.data).then(data => { return data; });
    }

    copy(data) {
        return JSON.parse(JSON.stringify(data));
    }
    showError(message) {
        this.messageService.clear();
        this.messageService.add({ severity: this.notificationType.error, summary: this.Translator.instant('lblError'), detail: this.Translator.instant(message) });
    }
    showWarning(message) {
        this.messageService.clear();
        this.messageService.add({ severity: this.notificationType.warn, summary: this.Translator.instant('lblWarn'), detail: this.Translator.instant(message) });
    }
    showSuccess(message) {
        this.messageService.clear();
        this.messageService.add({ severity: this.notificationType.success, summary: this.Translator.instant('lblSuccess'), detail: this.Translator.instant(message) });
    }

    convertDateforSubmition(date) {
        if (date != '') {
            return this.datePipe.transform(date, 'MM/dd/yyyy');
        }
        else {
            return '';
        }
    }

}
