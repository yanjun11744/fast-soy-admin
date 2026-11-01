import { request } from '../request';
import { createExcelFormData } from '@/utils/excel';
import type { ExcelDownload, ExcelImportOptions, ExcelPreview } from '@/utils/excel';

// ---- SettlementRate ----
export function fetchGetSettlementRateList(data?: Api.WeighbridgeSettlementManage.SettlementRateSearchParams) {
  return request<Api.WeighbridgeSettlementManage.SettlementRateList>({
    url: '/business/weighbridge_settlement/settlement_rates/search',
    method: 'post',
    data: data ?? {}
  });
}

export function fetchGetSettlementRate(id: string) {
  return request<Api.WeighbridgeSettlementManage.SettlementRate>({
    url: `/business/weighbridge_settlement/settlement_rates/${id}`,
    method: 'get'
  });
}

export function fetchAddSettlementRate(data?: Api.WeighbridgeSettlementManage.SettlementRateAddParams) {
  return request<null, 'json'>({
    url: '/business/weighbridge_settlement/settlement_rates',
    method: 'post',
    data
  });
}

export function fetchUpdateSettlementRate(data?: Api.WeighbridgeSettlementManage.SettlementRateUpdateParams) {
  return request<null, 'json'>({
    url: `/business/weighbridge_settlement/settlement_rates/${data?.id}`,
    method: 'patch',
    data
  });
}

export function fetchDeleteSettlementRate(data?: Api.WeighbridgeSettlementManage.CommonDeleteParams) {
  return request<null>({
    url: `/business/weighbridge_settlement/settlement_rates/${data?.id}`,
    method: 'delete'
  });
}

export function fetchBatchDeleteSettlementRate(data?: Api.WeighbridgeSettlementManage.CommonBatchDeleteParams) {
  return request<null>({
    url: '/business/weighbridge_settlement/settlement_rates',
    method: 'delete',
    data
  });
}


export function fetchExportSettlementRate(data?: Api.WeighbridgeSettlementManage.SettlementRateSearchParams & { ids?: string[] }) {
  return request<ExcelDownload>({ url: '/business/weighbridge_settlement/settlement_rates/export', method: 'post', data: data ?? {} });
}

export function fetchSettlementRateImportTemplate() {
  return request<ExcelDownload>({ url: '/business/weighbridge_settlement/settlement_rates/import-template' });
}

export function fetchPreviewImportSettlementRate(file: File, options?: ExcelImportOptions) {
  const data = createExcelFormData(file, options);
  return request<ExcelPreview>({ url: '/business/weighbridge_settlement/settlement_rates/import-preview', method: 'post', data, headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000 });
}

export function fetchImportSettlementRate(file: File, options?: ExcelImportOptions) {
  const data = createExcelFormData(file, options);
  return request<{ importedCount: number }>({ url: '/business/weighbridge_settlement/settlement_rates/import', method: 'post', data, headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000 });
}

// ---- WeighingTicket ----
export function fetchGetWeighingTicketList(data?: Api.WeighbridgeSettlementManage.WeighingTicketSearchParams) {
  return request<Api.WeighbridgeSettlementManage.WeighingTicketList>({
    url: '/business/weighbridge_settlement/weighing_tickets/search',
    method: 'post',
    data: data ?? {}
  });
}

export function fetchGetWeighingTicket(id: string) {
  return request<Api.WeighbridgeSettlementManage.WeighingTicket>({
    url: `/business/weighbridge_settlement/weighing_tickets/${id}`,
    method: 'get'
  });
}

export function fetchAddWeighingTicket(data?: Api.WeighbridgeSettlementManage.WeighingTicketAddParams) {
  return request<null, 'json'>({
    url: '/business/weighbridge_settlement/weighing_tickets',
    method: 'post',
    data
  });
}

export function fetchUpdateWeighingTicket(data?: Api.WeighbridgeSettlementManage.WeighingTicketUpdateParams) {
  return request<null, 'json'>({
    url: `/business/weighbridge_settlement/weighing_tickets/${data?.id}`,
    method: 'patch',
    data
  });
}

export function fetchDeleteWeighingTicket(data?: Api.WeighbridgeSettlementManage.CommonDeleteParams) {
  return request<null>({
    url: `/business/weighbridge_settlement/weighing_tickets/${data?.id}`,
    method: 'delete'
  });
}

export function fetchBatchDeleteWeighingTicket(data?: Api.WeighbridgeSettlementManage.CommonBatchDeleteParams) {
  return request<null>({
    url: '/business/weighbridge_settlement/weighing_tickets',
    method: 'delete',
    data
  });
}


export function fetchExportWeighingTicket(data?: Api.WeighbridgeSettlementManage.WeighingTicketSearchParams & { ids?: string[] }) {
  return request<ExcelDownload>({ url: '/business/weighbridge_settlement/weighing_tickets/export', method: 'post', data: data ?? {} });
}

export function fetchWeighingTicketImportTemplate() {
  return request<ExcelDownload>({ url: '/business/weighbridge_settlement/weighing_tickets/import-template' });
}

export function fetchPreviewImportWeighingTicket(file: File, options?: ExcelImportOptions) {
  const data = createExcelFormData(file, options);
  return request<ExcelPreview>({ url: '/business/weighbridge_settlement/weighing_tickets/import-preview', method: 'post', data, headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000 });
}

export function fetchImportWeighingTicket(file: File, options?: ExcelImportOptions) {
  const data = createExcelFormData(file, options);
  return request<{ importedCount: number }>({ url: '/business/weighbridge_settlement/weighing_tickets/import', method: 'post', data, headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000 });
}

