export class BaseResponse<T> {
    status: number;
    // data: T;
    data: any;
    message: string;
    token:string;
    
}