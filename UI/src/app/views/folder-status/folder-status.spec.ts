import { ComponentFixture, TestBed } from '@angular/core/testing';

import { FolderStatus } from './folder-status';

describe('FolderStatus', () => {
  let component: FolderStatus;
  let fixture: ComponentFixture<FolderStatus>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FolderStatus]
    })
    .compileComponents();

    fixture = TestBed.createComponent(FolderStatus);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
