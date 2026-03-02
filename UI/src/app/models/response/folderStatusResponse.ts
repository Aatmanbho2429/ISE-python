export type FolderStatusType = 'fully_loaded' | 'partial' | 'folder_missing';
export type FileStatusType   = 'loaded' | 'not_loaded';

export interface FolderSummary {
    folder:        string;
    indexed:       number;
    total_on_disk: number;
    not_loaded:    number;
    status:        FolderStatusType;
}

export interface FileNodeData {
    path:   string;
    status: FileStatusType;
}

export interface FolderStatusResponse {
    flat_list: FolderSummary[];
    tree:      TreeNode[];
}

// PrimeNG TreeNode
export interface TreeNode {
    label:     string;
    icon:      string;
    expanded?: boolean;
    leaf?:     boolean;
    data:      FolderSummary | FileNodeData;
    children?: TreeNode[];
}