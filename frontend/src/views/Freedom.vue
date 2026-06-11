<template>
  <div>
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <div>
            <span style="font-size: 18px; font-weight: bold">财务自由选股</span>
            <el-text type="info" style="margin-left: 12px">
              微淼体系：好公司 + 好价格 + 长期持有
            </el-text>
          </div>
          <el-date-picker v-model="selectedDate" type="date" placeholder="选择日期"
            value-format="YYYY-MM-DD" @change="loadData" />
        </div>
      </template>

      <!-- 选股标准说明 -->
      <el-alert type="info" :closable="false" style="margin-bottom: 20px">
        <template #title>
          <b>好公司标准：</b>ROE连续5年>15% | 毛利率>30% | 净利润现金含量>80% | 连续3年分红 | 股息率>3% | 负债率<60%
        </template>
      </el-alert>

      <!-- 股票列表 -->
      <el-table :data="stocks" stripe border style="width: 100%"
                :default-sort="{ prop: 'score', order: 'descending' }">
        <el-table-column prop="stock_code" label="代码" width="80" />
        <el-table-column prop="stock_name" label="名称" width="90" />
        <el-table-column prop="score" label="评分" width="70" sortable>
          <template #default="{ row }">
            <el-tag :type="row.score >= 80 ? 'danger' : row.score >= 60 ? 'warning' : 'info'" size="small">
              {{ row.score }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="ROE" width="70">
          <template #default="{ row }">
            <span :style="{ color: row.roe_avg > 20 ? '#f56c6c' : '#333' }">
              {{ row.roe_avg ? row.roe_avg.toFixed(1) + '%' : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="毛利率" width="75">
          <template #default="{ row }">{{ row.gross_margin ? row.gross_margin.toFixed(1) + '%' : '-' }}</template>
        </el-table-column>
        <el-table-column label="股息率" width="75">
          <template #default="{ row }">
            <span :style="{ color: row.dividend_yield > 3 ? '#67c23a' : '#333' }">
              {{ row.dividend_yield ? row.dividend_yield.toFixed(1) + '%' : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="PE" width="60">
          <template #default="{ row }">{{ row.pe ? row.pe.toFixed(1) : '-' }}</template>
        </el-table-column>
        <el-table-column label="负债率" width="70">
          <template #default="{ row }">{{ row.debt_ratio ? row.debt_ratio.toFixed(0) + '%' : '-' }}</template>
        </el-table-column>
        <el-table-column label="分红" width="55">
          <template #default="{ row }">{{ row.continuous_div_years }}年</template>
        </el-table-column>
        <el-table-column label="当前价" width="80">
          <template #default="{ row }">¥{{ row.current_price }}</template>
        </el-table-column>
        <el-table-column label="买入策略" width="180">
          <template #default="{ row }">
            <div style="font-size: 12px; line-height: 1.6">
              <div><b style="color: #409EFF">建议买入:</b> ¥{{ row.buy_price }}</div>
              <div><b style="color: #67c23a">好价格:</b> ¥{{ row.good_price }}</div>
              <div style="color: #999">{{ row.buy_type }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="止盈/止损" width="130">
          <template #default="{ row }">
            <div style="font-size: 12px">
              <div style="color: red">止盈: ¥{{ row.take_profit_price }}</div>
              <div style="color: green">止损: ¥{{ row.stop_loss_price }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="reasons" label="入选理由" min-width="200">
          <template #default="{ row }">
            <span style="font-size: 12px; color: #666">{{ row.reasons }}</span>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!stocks.length" description="暂无数据，请运行 weimu_screening.py 选股脚本" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const stocks = ref([])
const selectedDate = ref('')

const loadData = async (dateVal) => {
  try {
    const params = dateVal ? { date: dateVal } : {}
    const res = await axios.get('/api/weimu/list', { params })
    const data = res.data?.data || res.data?.result || []
    stocks.value = Array.isArray(data) ? data : []
  } catch (e) {
    console.error('loadData error:', e)
  }
}

onMounted(() => loadData())
</script>
