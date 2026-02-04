import { Component, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { PrimengComponentsModule } from './shared/primeng-components-module';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet,PrimengComponentsModule],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App {
  protected readonly title = signal('vynce-standalone');
}
