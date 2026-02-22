import { Routes } from '@angular/router';
import { ImageSearch } from './views/image-search/image-search';
import { Master } from './views/master/master';
import { LoadedFolder } from './views/loaded-folder/loaded-folder';

export const routes: Routes = [
    {
        path: '', component: Master,
        children: [
            {
                path: 'image', component: ImageSearch

            },
            {
                path: 'loaded-data', component: LoadedFolder

            }
        ]
    }
];
