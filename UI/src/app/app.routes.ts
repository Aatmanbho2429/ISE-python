import { Routes } from '@angular/router';
import { ImageSearch } from './views/image-search/image-search';
import { Master } from './views/master/master';
import { FolderStatus } from './views/folder-status/folder-status';
import { ActivityLog } from './views/activity-log/activity-log';
import { ContactUs } from './views/contact-us/contact-us';

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
            ,
            {
                path: 'contact-us', component: ContactUs

            }
        ]
    }
];
