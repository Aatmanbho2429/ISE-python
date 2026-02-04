export class menuItemListResponse{
    list: Array<menuItem>;
}
export class menuItem{
    path:string;
    icon:string;
    title:string;
    order:number;
}