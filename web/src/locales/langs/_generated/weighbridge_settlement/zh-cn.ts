// 自动生成（cli-gen-web）— 模块：磅单结算
// 由 web/src/locales/locale.ts 通过 import.meta.glob 自动合并到 zh-CN messages。
// 修改字段含义请改对应模型 description 后重跑 cli-gen-web；未涵盖的文案可在本文件追加。

export default {
  route: {
    'weighbridge-settlement': '磅单结算',
    'weighbridge-settlement_settlement-rate': '工序招采价格',
    'weighbridge-settlement_weighing-ticket': '磅单信息'
  },
  page: {
    weighbridge_settlement: {
      settlement: {
        details: '查看详情',
        lines: '关联订单明细',
        partNo: '项目号',
        orderNo: '订单号（选填）',
        name: '名称',
        netWeight: '净重/kg',
        grossWeight: '毛重/kg',
        quantity: '本次实际数量',
        theoreticalWeight: '理论毛重/kg',
        allocatedWeight: '分摊实际重量/kg',
        amount: '含税结算金额/元',
        taxUnitPrice: '每件含税单价',
        source: '录入来源',
        matched: '匹配订单',
        manual: '手动录入',
        searchOrders: '输入项目号搜索，选择具体订单',
        addLine: '添加明细',
        settle: '确认结算',
        settleConfirm: '结算后不可编辑或删除，确认继续？',
        settled: '已结算',
        unsettled: '未结算',
        preview: '试算结果（以保存结果为准）',
        totalTheoreticalWeight: '理论毛重合计/kg',
        refreshPrice: '使用当前工序最新价格',
        requiredLines: '请填写完整磅单及至少一条有效明细，毛重和数量必须大于零',
        previewFailed: '试算失败，请检查输入后重试',
        loadFailed: '加载失败，请关闭后重新打开',
        noOrders: '无匹配订单，可选择手动录入',
        retry: '重试试算'
      },
      common: { status: '状态', form: { status: '请选择状态' } },
      settlement_rate: {
        pageTitle: '工序招采价格',
        processName: '工序名称',
        price: '含税招采价格（元/kg）',
        enabled: '是否启用',
        form: {
          processName: '请输入工序名称',
          price: '请输入含税招采价格（元/kg）',
          enabled: '请输入是否启用'
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
          rate: '请选择工序招采价格'
        },
        addWeighingTicket: '新增磅单信息',
        editWeighingTicket: '编辑磅单信息'
      }
    }
  }
};
