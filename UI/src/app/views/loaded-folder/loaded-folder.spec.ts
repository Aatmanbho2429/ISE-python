import { ComponentFixture, TestBed } from '@angular/core/testing';

import { LoadedFolder } from './loaded-folder';

describe('LoadedFolder', () => {
  let component: LoadedFolder;
  let fixture: ComponentFixture<LoadedFolder>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LoadedFolder]
    })
    .compileComponents();

    fixture = TestBed.createComponent(LoadedFolder);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
