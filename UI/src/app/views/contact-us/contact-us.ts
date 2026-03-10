import { Component } from '@angular/core';
import { PrimengComponentsModule } from '../../shared/primeng-components-module';
import { TranslateModule } from '@ngx-translate/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-contact-us',
  imports: [PrimengComponentsModule, TranslateModule, CommonModule],
  templateUrl: './contact-us.html',
  styleUrl: './contact-us.scss',
})
export class ContactUs {
  email = 'aatmanbhoraniya@gmail.com';
}
