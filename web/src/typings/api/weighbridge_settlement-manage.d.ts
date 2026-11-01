declare namespace Api {
  namespace WeighbridgeSettlementManage {
    type CommonDeleteParams = { id: string };
    type CommonBatchDeleteParams = { ids: string[] };
    type CommonSearchParams = Pick<Common.PaginatingCommonParams, 'current' | 'size'>;

    // ---- SettlementRate ----
    type SettlementRate = Common.CommonRecord<{
      processName: string;
      price: number;
      enabled: boolean | null;
    }>;

    type SettlementRateAddParams = {
      processName: string;
      price: number;
      enabled?: boolean | null;
    };

    type SettlementRateUpdateParams = { id?: string } & Partial<SettlementRateAddParams>;

    type SettlementRateSearchParams = CommonType.RecordNullable<
      {
        processName?: string;
        enabled?: boolean;
      } & CommonSearchParams
    >;

    type SettlementRateList = Common.PaginatingQueryRecord<SettlementRate>;

    // ---- WeighingTicket ----
    type WeighingTicket = Common.CommonRecord<{
      ticketNo: string;
      weighingDate: string;
      weight: number;
      process: string;
      price: number;
      totalAmount: number;
      isSettled: boolean | null;
      revision: number | null;
      rateId: string;
    }>;

    type WeighingTicketAddParams = {
      ticketNo: string;
      weighingDate: string;
      weight: number;
      process: string;
      price: number;
      totalAmount: number;
      isSettled?: boolean | null;
      revision?: number | null;
      rateId: string;
    };

    type WeighingTicketUpdateParams = { id?: string } & Partial<WeighingTicketAddParams>;

    type WeighingTicketSearchParams = CommonType.RecordNullable<
      {
        weighingDateStart?: string;
        weighingDateEnd?: string;
        ticketNo?: string;
        process?: string;
        isSettled?: boolean;
        rateId?: string;
      } & CommonSearchParams
    >;

    type WeighingTicketList = Common.PaginatingQueryRecord<WeighingTicket>;

  }
}
