export interface ExcelDownload {
  filename: string;
  content: string;
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
