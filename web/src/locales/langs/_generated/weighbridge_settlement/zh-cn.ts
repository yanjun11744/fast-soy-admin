// 自动生成（cli-gen-web）— 模块：磅单结算
// 由 web/src/locales/locale.ts 通过 import.meta.glob 自动合并到 zh-CN messages。
// 修改字段含义请改对应模型 description 后重跑 cli-gen-web；未涵盖的文案可在本文件追加。

export default {
  route: {
    'weighbridge-settlement': '磅单结算',
    'weighbridge-settlement_settlement-rate': '工序招采价格',
    'weighbridge-settlement_weighing-ticket': '磅单信息',
  },
  page: {
    weighbridge_settlement: {
      common: { status: '状态', form: { status: '请选择状态' } },
      settlement_rate: {
        pageTitle: '工序招采价格',
        processName: '工序名称',
        price: '含税招采价格（元/kg）',
        enabled: '是否启用',
        form: {
          processName: '请输入工序名称',
          price: '请输入含税招采价格（元/kg）',
          enabled: '请输入是否启用',
        },
        addSettlementRate: '新增工序招采价格',
        editSettlementRate: '编辑工序招采价格'
      },
      weighing_ticket: {
        pageTitle: '磅单信息',
        ticketNo: '磅单编号',
        weighingDate: '过磅日期',
        weight: '实际过磅重量/kg',
        process: '工序名称快照',
        price: '含税价格快照（元/kg）',
        totalAmount: '含税总金额/元',
        isSettled: '是否已结算',
        revision: '修订版本',
        rate: '工序招采价格',
        form: {
          ticketNo: '请输入磅单编号',
          weighingDate: '请输入过磅日期',
          weight: '请输入实际过磅重量/kg',
          process: '请输入工序名称快照',
          price: '请输入含税价格快照（元/kg）',
          totalAmount: '请输入含税总金额/元',
          isSettled: '请输入是否已结算',
          revision: '请输入修订版本',
          rate: '请选择工序招采价格',
        },
        addWeighingTicket: '新增磅单信息',
        editWeighingTicket: '编辑磅单信息'
      },
    },
  },
};
