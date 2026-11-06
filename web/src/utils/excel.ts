export interface ExcelDownload {
  filename: string;
  content: string;
}

export interface ExcelImportOptions {
  sheet?: string;
  headerRow?: number;
  columns?: (string | null)[];
}

export interface ExcelPreview {
  sheets: string[];
  sheet: string | null;
  headerRow: number | null;
  fields: { name: string; title: string; required: boolean }[];
  columns: { index: number; header: string; field: string | null; samples: string[] }[];
  rowCount: number;
  errors: string[];
}

type ExcelResult<T> = Promise<{ data: T | null; error: unknown }>;
export interface ExcelImportResult {
  importedCount: number;
  createdCount?: number;
  updatedCount?: number;
}
export type ExcelImportApi = (file: File, options?: ExcelImportOptions) => ExcelResult<ExcelImportResult>;
export type ExcelPreviewApi = (file: File, options?: ExcelImportOptions) => ExcelResult<ExcelPreview>;

export function createExcelFormData(file: File, options?: ExcelImportOptions) {
  const data = new FormData();
  data.append('file', file);
  if (options) data.append('options', JSON.stringify(options));
  return data;
}

export function downloadExcel(file: ExcelDownload) {
  const bytes = Uint8Array.from(atob(file.content), character => character.charCodeAt(0));
  const blob = new Blob([bytes], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = file.filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
