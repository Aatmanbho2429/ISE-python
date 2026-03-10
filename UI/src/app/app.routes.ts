import { Routes } from '@angular/router';
import { ImageSearch } from './views/image-search/image-search';
import { Master } from './views/master/master';
import { FolderStatus } from './views/folder-status/folder-status';
import { ActivityLog } from './views/activity-log/activity-log';

export const routes: Routes = [
    {
        path: '', component: Master,
        children: [
            {
                path: 'image', component: ImageSearch

            },
            {
                path: 'loaded-data', component: FolderStatus

            },
            {
                path: 'activity-log', component: ActivityLog

            }
        ]
    }
];
