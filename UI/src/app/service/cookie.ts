import { Injectable } from '@angular/core';
import { CookieService } from 'ngx-cookie-service';
import * as CryptoJS from 'crypto-js';

@Injectable({
  providedIn: 'root',
})
export class Cookie {
  public hostName: string = this.getDomainName(window.location.hostname);
    // public hostName: string = window.location.host;
    //public hostName: string = 'app-cpesaportal-dev-001.azurewebsites.net';
    private secretKey = 'aHYtde568polkJHYUG7Yh5FRDs';
    constructor(private service: CookieService) { }

    GetCookie(key: string) {
        return CryptoJS.AES.decrypt(this.service.get(key), this.secretKey.trim()).toString(CryptoJS.enc.Utf8);
    }

    SetCookie(key: string, data: any) {
        //console.log("hostName Set:: " + this.hostName);
        
        this.service.set(key, CryptoJS.AES.encrypt(data.toString(), this.secretKey), { sameSite: 'None', secure: true, expires: 1, domain: this.hostName, path: '/' });
    }

    DeleteCookie(key) {
        this.service.delete(key, '/', this.hostName, true, 'None');
        this.service.delete(key, '/dashboard', this.hostName, true, 'None');
        this.service.delete(key, '/admin', this.hostName, true, 'None');
    }

    DeleteAllCookies() {
        this.service.deleteAll('/', this.hostName, true, 'None');
        this.service.deleteAll('/dashboard', this.hostName, true, 'None');
        this.service.deleteAll('/admin', this.hostName, true, 'None');
    }

    GetAllCookie() {
        return this.service.getAll();
    }

    getDomainName(hostName) {
        return hostName.substring(hostName.lastIndexOf(".", hostName.lastIndexOf(".") - 1) + 1);
    }
}
