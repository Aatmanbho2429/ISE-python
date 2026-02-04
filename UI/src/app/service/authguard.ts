import { Injectable } from '@angular/core';
import {
  CanActivate,
  CanActivateChild,
  ActivatedRouteSnapshot,
  RouterStateSnapshot,
  Router,
  UrlTree
} from '@angular/router';
import { Cookie } from './cookie';
import { JwtHelperService } from '@auth0/angular-jwt';
import { CookieConstant } from '../models/const/cookieConstant';

@Injectable({
  providedIn: 'root'
})
export class Authguard implements CanActivate, CanActivateChild {

  constructor(
    private router: Router,
    private cookie: Cookie,
    private jwtHelper: JwtHelperService
  ) {}

  private checkAuth(state: RouterStateSnapshot): boolean | UrlTree {
    const userId = this.cookie.GetCookie(CookieConstant.Web_UserId);
    const token = this.cookie.GetCookie(CookieConstant.Web_Token);

    if (!userId || !token || this.jwtHelper.isTokenExpired(token)) {
      this.cookie.DeleteAllCookies();
      return this.router.createUrlTree(['/login'], {
        queryParams: { returnUrl: state.url }
      });
    }

    return true;
  }

  canActivate(
    route: ActivatedRouteSnapshot,
    state: RouterStateSnapshot
  ): boolean | UrlTree {
    return this.checkAuth(state);
  }

  canActivateChild(
    childRoute: ActivatedRouteSnapshot,
    state: RouterStateSnapshot
  ): boolean | UrlTree {
    return this.checkAuth(state);
  }
}
