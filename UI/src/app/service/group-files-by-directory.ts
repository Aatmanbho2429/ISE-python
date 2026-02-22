// ─── Interfaces ───────────────────────────────────────────────────────────────

export interface FileEntry {
  id: number;
  hash: string;
}

export interface RawFileIndex {
  next_id: number;
  files: Record<string, FileEntry>;
}

export interface FileNode {
  name: string;
  fullPath: string;
  id: number;
  hash: string;
}

export interface DirectoryNode {
  name: string;
  fullPath: string;
  files: FileNode[];
  subDirectories: Record<string, DirectoryNode>;
  totalFiles?: number; // populated after build
}

export interface GroupedFileTree {
  root: DirectoryNode;
  totalFiles: number;
  totalDirectories: number;
}

// ─── Core Grouping Logic ──────────────────────────────────────────────────────

/**
 * Splits a Windows or Unix path into its parts.
 * e.g. "E:\\Projects\\foo\\bar.jpg" → ["E:", "Projects", "foo", "bar.jpg"]
 */
function splitPath(filePath: string): string[] {
  return filePath.split(/[\\/]+/).filter(Boolean);
}

/**
 * Recursively counts all files in a directory and its sub-directories.
 */
function countFiles(dir: DirectoryNode): number {
  const ownFiles = dir.files.length;
  const childFiles = Object.values(dir.subDirectories).reduce(
    (sum, sub) => sum + countFiles(sub),
    0
  );
  dir.totalFiles = ownFiles + childFiles;
  return dir.totalFiles;
}

/**
 * Builds a nested DirectoryNode tree from the flat file index.
 */
export function groupByDirectory(raw: RawFileIndex): GroupedFileTree {
  const root: DirectoryNode = {
    name: '',
    fullPath: '',
    files: [],
    subDirectories: {},
  };

  let totalDirectories = 0;

  for (const [fullPath, entry] of Object.entries(raw.files)) {
    const parts = splitPath(fullPath);

    // Last part is the filename, everything before is folders
    const fileName = parts[parts.length - 1];
    const dirParts = parts.slice(0, -1);

    let current = root;

    // Walk/create the directory chain
    let builtPath = '';
    for (const part of dirParts) {
      builtPath = builtPath ? `${builtPath}\\${part}` : part;

      if (!current.subDirectories[part]) {
        current.subDirectories[part] = {
          name: part,
          fullPath: builtPath,
          files: [],
          subDirectories: {},
        };
        totalDirectories++;
      }

      current = current.subDirectories[part];
    }

    // Add the file to the deepest directory
    current.files.push({
      name: fileName,
      fullPath,
      id: entry.id,
      hash: entry.hash,
    });
  }

  // Compute totalFiles for every node
  countFiles(root);

  return {
    root,
    totalFiles: raw.next_id,
    totalDirectories,
  };
}

// ─── Flat List Helper ─────────────────────────────────────────────────────────

export interface FlatDirectory {
  path: string;
  depth: number;
  fileCount: number;       // files directly in this folder
  totalFiles: number;      // files in this folder + all sub-folders
  subDirCount: number;
  files: FileNode[];
}

/**
 * Flattens the tree into an array of directories sorted by path.
 * Useful for rendering in Angular p-tree or custom components.
 */
export function flattenTree(
  node: DirectoryNode,
  depth = 0,
  result: FlatDirectory[] = []
): FlatDirectory[] {
  if (node.fullPath) {
    result.push({
      path: node.fullPath,
      depth,
      fileCount: node.files.length,
      totalFiles: node.totalFiles ?? 0,
      subDirCount: Object.keys(node.subDirectories).length,
      files: node.files,
    });
  }

  for (const sub of Object.values(node.subDirectories)) {
    flattenTree(sub, depth + 1, result);
  }

  return result;
}

// ─── PrimeNG TreeNode Adapter ─────────────────────────────────────────────────

export interface PrimeTreeNode {
  label: string;
  data: { fullPath: string; fileCount: number; totalFiles: number; type: 'folder' | 'file'; hash?: string; id?: number };
  icon: string;
  expandedIcon?: string;
  collapsedIcon?: string;
  children?: PrimeTreeNode[];
  leaf?: boolean;
}

/**
 * Converts the GroupedFileTree into PrimeNG TreeNode[] format,
 * ready to drop into <p-tree> or <p-treeTable>.
 */
export function toPrimeNgTreeNodes(node: DirectoryNode): PrimeTreeNode[] {
  const subDirNodes: PrimeTreeNode[] = Object.values(node.subDirectories).map(
    (sub) => ({
      label: `${sub.name}  (${sub.totalFiles} files)`,
      icon: 'pi pi-folder',
      expandedIcon: 'pi pi-folder-open',
      collapsedIcon: 'pi pi-folder',
      data: {
        fullPath: sub.fullPath,
        fileCount: sub.files.length,
        totalFiles: sub.totalFiles ?? 0,
        type: 'folder' as const,
        exists: (sub as any).exists ?? true,
      },
      children: toPrimeNgTreeNodes(sub),
    })
  );

  const fileNodes: PrimeTreeNode[] = node.files.map((f) => ({
    label: f.name,
    icon: 'pi pi-image',
    leaf: true,
    data: {
      fullPath: f.fullPath,
      fileCount: 1,
      totalFiles: 1,
      type: 'file' as const,
      hash: f.hash,
      id: f.id,
      exists: (f as any).exists ?? true,
    },
  }));

  return [...subDirNodes, ...fileNodes];
}

// ─── Usage Example ────────────────────────────────────────────────────────────

/*

// In your Angular component:

import rawData from './your-index.json';
import { groupByDirectory, flattenTree, toPrimeNgTreeNodes, GroupedFileTree } from './group-files-by-directory';

@Component({ ... })
export class FileExplorerComponent implements OnInit {

  tree!: GroupedFileTree;
  primeNodes: PrimeTreeNode[] = [];
  flatDirs: FlatDirectory[] = [];

  ngOnInit() {
    this.tree = groupByDirectory(rawData);

    // For PrimeNG <p-tree>
    this.primeNodes = toPrimeNgTreeNodes(this.tree.root);

    // For custom flat rendering
    this.flatDirs = flattenTree(this.tree.root);

    console.log('Total files:', this.tree.totalFiles);
    console.log('Total directories:', this.tree.totalDirectories);
  }
}

// Template usage with PrimeNG:
// <p-tree [value]="primeNodes" [filter]="true"></p-tree>

*/
