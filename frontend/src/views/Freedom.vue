<template>
  <div>
    <!-- 市场PE估值分析卡片 -->
    <el-card style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-size: 16px; font-weight: bold">📊 市场估值分析</span>
          <el-button size="small" @click="loadMarketAnalysis" :loading="loadingAnalysis">
            刷新数据
          </el-button>
        </div>
      </template>

      <div v-if="marketAnalysis" style="display: flex; gap: 24px; flex-wrap: wrap; align-items: flex-start">
        <div style="text-align: center; min-width: 120px">
          <div style="font-size: 36px; font-weight: bold" :style="{ color: peColor }">
            {{ marketAnalysis.market_pe }}
          </div>
          <div style="color: #999; font-size: 12px">深证A股PE</div>
        </div>

        <div style="text-align: center; min-width: 100px">
          <el-tag :type="peTagType" size="large" style="font-size: 16px; padding: 8px 16px">
            {{ marketAnalysis.analysis?.level || '-' }}
          </el-tag>
          <div style="color: #999; font-size: 12px; margin-top: 4px">估值水平</div>
        </div>

        <div style="text-align: center; min-width: 100px">
          <div style="font-size: 24px; font-weight: bold; color: #409EFF">
            {{ marketAnalysis.bond_yield }}%
          </div>
          <div style="color: #999; font-size: 12px">10年国债收益率</div>
        </div>

        <div style="flex: 1; min-width: 300px">
          <el-alert :type="alertType" :title="marketAnalysis.analysis?.advice || ''" :closable="false" show-icon />
          <p style="font-size: 13px; color: #666; margin-top: 8px; line-height: 1.8">
            {{ marketAnalysis.analysis?.description || '' }}
          </p>
        </div>
      </div>
      <el-skeleton v-else :rows="2" animated />
    </el-card>

    <!-- 资产配置建议卡片 -->
    <el-card style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-size: 16px; font-weight: bold">💡 资产配置建议</span>
          <div style="display: flex; align-items: center; gap: 12px">
            <el-input-number v-model="capitalInput" :min="10000" :step="10000"
              :precision="0" style="width: 160px" />
            <span style="color: #999; font-size: 13px">元</span>
            <el-button type="primary" size="small" @click="loadAllocation">生成方案</el-button>
          </div>
        </div>
      </template>

      <div v-if="allocation">
        <!-- 概览 -->
        <div style="display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 20px">
          <el-statistic title="可投资资金" :value="allocation.investable_capital" suffix="元" />
          <el-statistic title="应急预留" :value="allocation.emergency_fund" suffix="元" />
          <el-statistic title="年度保费预算" :value="allocation.insurance_budget" suffix="元" />
          <el-statistic title="市场估值" :value="allocation.market_level" />
        </div>

        <!-- 配置饼图（文字版） -->
        <el-divider content-position="left">推荐配置比例</el-divider>
        <div style="display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px">
          <div v-for="item in allocation.allocation" :key="item.category"
               style="border: 1px solid #eee; border-radius: 8px; padding: 12px 16px; min-width: 150px; flex: 1">
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: bold; font-size: 14px">{{ item.name }}</span>
              <el-tag :type="tagTypeForCategory(item.type)" size="small">
                {{ item.ratio }}%
              </el-tag>
            </div>
            <div style="font-size: 20px; font-weight: bold; color: #303133; margin-top: 4px">
              ¥{{ formatMoney(item.amount) }}
            </div>
            <el-progress :percentage="item.ratio" :stroke-width="6" :show-text="false"
              :color="colorForCategory(item.type)" style="margin-top: 6px" />
          </div>
        </div>

        <!-- 具体工具建议 -->
        <el-divider content-position="left">具体投资工具</el-divider>
        <el-collapse>
          <el-collapse-item v-for="tool in allocation.tools" :key="tool.category"
            :title="`${tool.name} — ¥${formatMoney(tool.amount)}`">
            <div style="padding: 0 12px">
              <div style="margin-bottom: 8px">
                <el-tag size="small" type="info">风险: {{ tool.risk }}</el-tag>
                <el-tag size="small" type="success" style="margin-left: 8px">
                  预期收益: {{ tool.expected_return }}
                </el-tag>
                <el-tag size="small" style="margin-left: 8px">
                  持有周期: {{ tool.holding_period }}
                </el-tag>
              </div>
              <ul style="color: #666; font-size: 13px; line-height: 2; padding-left: 18px">
                <li v-for="(s, i) in tool.suggestions" :key="i">{{ s }}</li>
              </ul>
            </div>
          </el-collapse-item>
        </el-collapse>

        <!-- 操作步骤 -->
        <el-divider content-position="left">执行步骤</el-divider>
        <el-steps direction="vertical" :active="0" finish-status="wait">
          <el-step v-for="step in allocation.steps" :key="step.order"
            :title="step.title" :description="step.description">
            <template #description>
              <div style="font-size: 13px; color: #666; line-height: 1.8">
                {{ step.description }}
                <div style="margin-top: 4px">
                  <el-tag size="small" type="warning">{{ step.action }}</el-tag>
                </div>
              </div>
            </template>
          </el-step>
        </el-steps>
      </div>

      <el-empty v-else description="输入资金金额，点击「生成方案」获取配置建议" />
    </el-card>

    <!-- AI进化建议卡片 -->
    <el-card style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-size: 16px; font-weight: bold">🧬 AI进化建议</span>
          <div style="display: flex; gap: 8px">
            <el-button type="warning" size="small" @click="triggerEvolve" :loading="evolving">
              {{ evolving ? '进化中...' : '触发进化' }}
            </el-button>
            <el-button size="small" @click="loadAdvice">刷新</el-button>
          </div>
        </div>
      </template>

      <div v-if="advice">
        <div v-if="advice.updated_at" style="color: #999; font-size: 12px; margin-bottom: 12px">
          最后更新: {{ advice.updated_at }}
        </div>

        <!-- 投资注意事项 -->
        <div v-if="advice.investment_notes && advice.investment_notes.length" style="margin-bottom: 16px">
          <div style="font-weight: bold; margin-bottom: 8px; color: #409EFF">📌 投资注意事项</div>
          <ul style="padding-left: 18px; color: #333; line-height: 2; font-size: 13px">
            <li v-for="(note, i) in advice.investment_notes" :key="i">{{ note }}</li>
          </ul>
        </div>

        <!-- 风险警示 -->
        <div v-if="advice.risk_warnings && advice.risk_warnings.length" style="margin-bottom: 16px">
          <div style="font-weight: bold; margin-bottom: 8px; color: #f56c6c">⚠️ 风险警示</div>
          <ul style="padding-left: 18px; color: #f56c6c; line-height: 2; font-size: 13px">
            <li v-for="(w, i) in advice.risk_warnings" :key="i">{{ w }}</li>
          </ul>
        </div>

        <!-- 配置建议 -->
        <div v-if="advice.allocation_advice">
          <div style="font-weight: bold; margin-bottom: 8px; color: #67c23a">💰 配置方向</div>
          <p style="color: #333; font-size: 13px">{{ advice.allocation_advice }}</p>
        </div>
      </div>

      <el-empty v-else description="点击「触发进化」让AI分析最新政策和行情" :image-size="60" />
    </el-card>

    <!-- 选股结果卡片 -->
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <div>
            <span style="font-size: 18px; font-weight: bold">💰 财务自由选股</span>
            <el-text type="info" style="margin-left: 12px">
              微淼体系：好公司 + 好价格 + 长期持有
            </el-text>
          </div>
          <div style="display: flex; align-items: center; gap: 12px">
            <el-date-picker v-model="selectedDate" type="date" placeholder="选择日期"
              value-format="YYYY-MM-DD" @change="loadData" style="width: 150px" />
            <el-button type="primary" @click="triggerRun" :loading="running">
              {{ running ? '筛选中...' : '运行筛选' }}
            </el-button>
            <el-button @click="triggerQuick" :loading="quickRunning">
              快速更新估值
            </el-button>
          </div>
        </div>
      </template>

      <!-- 筛选标准说明 -->
      <el-alert type="info" :closable="false" style="margin-bottom: 16px">
        <template #title>
          <div style="line-height: 1.8">
            <b>海选：</b>连续5年 ROE>15% + 毛利率>30% + 现金含量>80% + 连续3年分红<br/>
            <b>精选：</b>ROE>20% + 毛利率>40% + 现金含量>100% + 负债率&lt;60% + 连续5年分红<br/>
            <b>买入：</b>深证A股PE&lt;20 且 个股PE&lt;15 且 股息率 > 10年国债收益率
          </div>
        </template>
      </el-alert>

      <!-- 筛选进度 -->
      <el-alert v-if="progress && progress.status === 'running'"
        type="warning" :closable="false" style="margin-bottom: 16px">
        <template #title>
          筛选进行中: {{ progress.message || '请稍候...' }}
        </template>
      </el-alert>

      <!-- 股票列表 -->
      <el-table :data="stocks" stripe border style="width: 100%"
                :default-sort="{ prop: 'score', order: 'descending' }">
        <el-table-column prop="stock_code" label="代码" width="80" />
        <el-table-column prop="stock_name" label="名称" width="120" show-overflow-tooltip />
        <el-table-column width="85" sortable sort-by="valuation">
          <template #header>
            <el-tooltip placement="top"
              content="估值水平（非持仓状态）：低估=好价格可买入；合理=估值适中；高估=偏贵建议卖出；观望=暂不符合买入条件。">
              <span style="border-bottom:1px dashed #999; cursor:help">估值</span>
            </el-tooltip>
          </template>
          <template #default="{ row }">
            <el-tag v-if="row.valuation === 'buy'" type="danger" size="small">低估·可买</el-tag>
            <el-tag v-else-if="row.valuation === 'hold'" type="warning" size="small">估值合理</el-tag>
            <el-tag v-else-if="row.valuation === 'sell'" type="info" size="small">高估·可卖</el-tag>
            <el-tag v-else size="small">观望</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="score" label="评分" width="65" sortable>
          <template #default="{ row }">
            <el-tag :type="row.score >= 70 ? 'danger' : row.score >= 50 ? 'warning' : 'info'" size="small">
              {{ row.score }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="ROE均值" width="85">
          <template #default="{ row }">
            <span :style="{ color: row.roe_avg >= 25 ? '#f56c6c' : row.roe_avg >= 20 ? '#e6a23c' : '#333' }">
              {{ row.roe_avg ? Number(row.roe_avg).toFixed(1) + '%' : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="毛利率" width="80">
          <template #default="{ row }">
            {{ row.gross_margin_avg ? Number(row.gross_margin_avg).toFixed(1) + '%' : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="现金含量" width="85">
          <template #default="{ row }">
            <span :style="{ color: row.cash_ratio_avg >= 100 ? '#67c23a' : '#333' }">
              {{ row.cash_ratio_avg ? Number(row.cash_ratio_avg).toFixed(0) + '%' : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="负债率" width="75">
          <template #default="{ row }">
            <span :style="{ color: row.debt_ratio >= 50 ? '#f56c6c' : '#333' }">
              {{ row.debt_ratio ? Number(row.debt_ratio).toFixed(0) + '%' : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="个股PE" width="75" sortable sort-by="pe">
          <template #default="{ row }">
            <span :style="{ color: row.pe && row.pe < 15 ? '#67c23a' : row.pe > 50 ? '#f56c6c' : '#333' }">
              {{ row.pe ? Number(row.pe).toFixed(1) : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="股息率" width="75">
          <template #default="{ row }">
            <span :style="{ color: row.dividend_yield > 3 ? '#67c23a' : '#333' }">
              {{ row.dividend_yield ? Number(row.dividend_yield).toFixed(2) + '%' : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="连续分红" width="80">
          <template #default="{ row }">
            {{ row.continuous_dividend_years || 0 }}年
          </template>
        </el-table-column>
        <el-table-column label="当前价格" width="90" sortable sort-by="current_price">
          <template #default="{ row }">
            <span v-if="row.current_price" style="font-weight: bold; color: #303133">
              ¥{{ Number(row.current_price).toFixed(2) }}
            </span>
            <span v-else style="color: #999">-</span>
          </template>
        </el-table-column>
        <el-table-column width="110">
          <template #header>
            <el-tooltip placement="top"
              content="合理买入价 = 每股收益 × 15（PE=15 的价位，微淼的好价格上限）。当前价 ≤ 此价即为好价格，可买入。">
              <span style="border-bottom:1px dashed #999; cursor:help">合理买入价</span>
            </el-tooltip>
          </template>
          <template #default="{ row }">
            <div v-if="row.suggest_buy_price">
              <span style="color: #67c23a; font-weight: bold">
                ≤¥{{ Number(row.suggest_buy_price).toFixed(2) }}
              </span>
              <el-tag v-if="row.current_price && row.current_price <= row.suggest_buy_price"
                type="success" size="small" effect="plain" style="margin-left:2px">现价合适</el-tag>
            </div>
            <span v-else style="color: #999">-</span>
          </template>
        </el-table-column>
        <el-table-column width="110">
          <template #header>
            <el-tooltip placement="top"
              content="高估价 = 每股收益 × 30（PE=30 的价位，微淼的高估分界线）。当前价 ≥ 此价即为高估，应考虑卖出。">
              <span style="border-bottom:1px dashed #999; cursor:help">高估价</span>
            </el-tooltip>
          </template>
          <template #default="{ row }">
            <span v-if="row.suggest_sell_price" style="color: #f56c6c; font-weight: bold">
              ≥¥{{ Number(row.suggest_sell_price).toFixed(2) }}
            </span>
            <span v-else style="color: #999">-</span>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!stocks.length && !running" description="暂无数据，请点击「运行筛选」" />
    </el-card>

    <!-- 投资工具推荐卡片 -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-size: 16px; font-weight: bold">🛠️ 其他投资工具推荐</span>
          <el-button size="small" @click="loadTools" :loading="loadingTools">刷新数据</el-button>
        </div>
      </template>

      <div v-if="tools">
        <el-tabs>
          <!-- REITs -->
          <el-tab-pane label="REITs">
            <el-alert :title="tools.reits?.description" type="info" :closable="false" style="margin-bottom: 12px" />
            <div style="margin-bottom: 8px; font-size: 12px; color: #999">
              买入标准: {{ tools.reits?.buy_criteria }}
            </div>
            <el-table :data="tools.reits?.items || []" stripe size="small" max-height="300">
              <el-table-column prop="code" label="代码" width="80" />
              <el-table-column prop="name" label="名称" width="180" />
              <el-table-column label="价格" width="80">
                <template #default="{row}">{{ row.price ? '¥'+row.price : '-' }}</template>
              </el-table-column>
              <el-table-column label="涨跌" width="75">
                <template #default="{row}">
                  <span v-if="row.change_pct" :style="{color: row.change_pct>0?'red':'green'}">
                    {{ row.change_pct>0?'+':'' }}{{ row.change_pct }}%
                  </span>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column prop="category" label="类型" width="120" />
              <el-table-column prop="market" label="市场" width="60" />
            </el-table>
          </el-tab-pane>

          <!-- 货币基金 -->
          <el-tab-pane label="货币基金">
            <el-alert :title="tools.money_fund?.description" type="success" :closable="false" style="margin-bottom: 12px" />
            <div style="margin-bottom: 8px; font-size: 12px; color: #999">
              选择标准: {{ tools.money_fund?.buy_criteria }}
            </div>
            <el-table :data="tools.money_fund?.items || []" stripe size="small" max-height="300">
              <el-table-column prop="code" label="代码" width="80" />
              <el-table-column prop="name" label="名称" min-width="180" />
              <el-table-column label="7日年化" width="90">
                <template #default="{row}">
                  <span style="color: #f56c6c; font-weight: bold">
                    {{ row.yield_7d ? row.yield_7d+'%' : '-' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="万份收益" width="80">
                <template #default="{row}">{{ row.yield_10k || '-' }}</template>
              </el-table-column>
              <el-table-column prop="note" label="备注" width="120" />
            </el-table>
          </el-tab-pane>

          <!-- 债券基金 -->
          <el-tab-pane label="债券基金">
            <el-alert :title="tools.bond_fund?.description" type="warning" :closable="false" style="margin-bottom: 12px" />
            <div style="margin-bottom: 8px; font-size: 12px; color: #999">
              选择标准: {{ tools.bond_fund?.buy_criteria }}
            </div>
            <el-table :data="tools.bond_fund?.items || []" stripe size="small" max-height="300">
              <el-table-column prop="code" label="代码" width="80" />
              <el-table-column prop="name" label="名称" min-width="200" />
              <el-table-column prop="type" label="类型" width="90">
                <template #default="{row}">
                  <el-tag size="small" :type="row.type==='短债基金'?'success':'info'">
                    {{ row.type }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="近1年" width="80">
                <template #default="{row}">
                  <span v-if="row.yield_1y" style="color: #67c23a">{{ row.yield_1y }}%</span>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column prop="note" label="备注" width="120" />
            </el-table>
          </el-tab-pane>

          <!-- 国债逆回购 -->
          <el-tab-pane label="逆回购">
            <el-alert :title="tools.reverse_repo?.description" type="success" :closable="false" style="margin-bottom: 12px" />
            <div style="margin-bottom: 8px; font-size: 12px; color: #999">
              操作建议: {{ tools.reverse_repo?.buy_criteria }}
            </div>
            <el-table :data="tools.reverse_repo?.items || []" stripe size="small">
              <el-table-column prop="code" label="代码" width="80" />
              <el-table-column prop="name" label="品种" width="180" />
              <el-table-column prop="period" label="期限" width="80" />
              <el-table-column label="当前年化利率" width="120">
                <template #default="{row}">
                  <span v-if="row.rate" style="color: #f56c6c; font-weight: bold; font-size: 16px">
                    {{ row.rate }}%
                  </span>
                  <span v-else style="color: #999">非交易时间</span>
                </template>
              </el-table-column>
              <el-table-column prop="note" label="备注" min-width="150" />
            </el-table>
            <div v-if="tools.reverse_repo?.tips" style="margin-top: 12px; padding: 12px; background: #f5f7fa; border-radius: 4px">
              <div style="font-weight: bold; margin-bottom: 8px">💡 操作技巧</div>
              <ul style="padding-left: 18px; color: #666; font-size: 13px; line-height: 2">
                <li v-for="(tip, i) in tools.reverse_repo.tips" :key="i">{{ tip }}</li>
              </ul>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>

      <el-skeleton v-else-if="loadingTools" :rows="4" animated />
      <el-empty v-else description="点击「刷新数据」获取最新投资工具推荐" :image-size="60" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const stocks = ref([])
const selectedDate = ref('')
const running = ref(false)
const quickRunning = ref(false)
const progress = ref(null)
const marketAnalysis = ref(null)
const loadingAnalysis = ref(false)
const allocation = ref(null)
const capitalInput = ref(200000)
const advice = ref(null)
const evolving = ref(false)
const tools = ref(null)
const loadingTools = ref(false)

// 根据PE值确定颜色
const peColor = computed(() => {
  const pe = marketAnalysis.value?.market_pe
  if (!pe) return '#999'
  if (pe < 20) return '#67c23a'
  if (pe < 30) return '#409EFF'
  if (pe < 40) return '#e6a23c'
  return '#f56c6c'
})

const peTagType = computed(() => {
  const zone = marketAnalysis.value?.analysis?.zone
  if (zone === 'very_low' || zone === 'low') return 'success'
  if (zone === 'fair_low' || zone === 'fair') return 'warning'
  return 'danger'
})

const alertType = computed(() => {
  const analysis = marketAnalysis.value?.analysis
  if (!analysis) return 'info'
  if (analysis.suitable_for_buying) return 'success'
  if (analysis.should_sell) return 'error'
  return 'warning'
})

const tagTypeForCategory = (type) => {
  if (type === 'core') return 'danger'
  if (type === 'cash') return 'success'
  if (type === 'defense') return 'info'
  return ''
}

const colorForCategory = (type) => {
  if (type === 'core') return '#f56c6c'
  if (type === 'cash') return '#67c23a'
  if (type === 'defense') return '#409EFF'
  return '#909399'
}

const formatMoney = (amount) => {
  if (!amount) return '0'
  if (amount >= 10000) return (amount / 10000).toFixed(1) + '万'
  return amount.toLocaleString()
}

// 加载市场PE分析
const loadMarketAnalysis = async () => {
  loadingAnalysis.value = true
  try {
    const res = await axios.get('/api/weimu/market-analysis')
    marketAnalysis.value = res.data?.data || null
  } catch (e) {
    console.error('loadMarketAnalysis error:', e)
  } finally {
    loadingAnalysis.value = false
  }
}

// 加载资产配置建议
const loadAllocation = async () => {
  try {
    const res = await axios.get('/api/weimu/allocation', {
      params: { capital: capitalInput.value }
    })
    allocation.value = res.data?.data || null
  } catch (e) {
    console.error('loadAllocation error:', e)
    ElMessage.error('获取配置建议失败')
  }
}

// 加载选股数据
const loadData = async (dateVal) => {
  try {
    const params = dateVal ? { date: dateVal } : {}
    const res = await axios.get('/api/weimu/list', { params })
    const data = res.data?.data || []
    stocks.value = Array.isArray(data) ? data : []
  } catch (e) {
    console.error('loadData error:', e)
  }
}

// 触发完整筛选
const triggerRun = async () => {
  running.value = true
  try {
    const res = await axios.post('/api/weimu/run')
    if (res.data?.code === 0) {
      ElMessage.success('筛选任务已启动，全A股扫描需要较长时间...')
      pollProgress()
    } else {
      ElMessage.warning(res.data?.message || '启动失败')
      running.value = false
    }
  } catch (e) {
    ElMessage.error('触发失败')
    running.value = false
  }
}

// 快速更新估值
const triggerQuick = async () => {
  quickRunning.value = true
  try {
    const res = await axios.post('/api/weimu/quick')
    ElMessage.success(res.data?.message || '估值更新完成')
    await loadData()
    await loadMarketAnalysis()
  } catch (e) {
    ElMessage.error('更新失败')
  } finally {
    quickRunning.value = false
  }
}

// 轮询筛选进度
const pollProgress = () => {
  const timer = setInterval(async () => {
    try {
      const res = await axios.get('/api/weimu/status')
      progress.value = res.data?.data || null

      if (progress.value?.status === 'completed' || progress.value?.status === 'failed') {
        clearInterval(timer)
        running.value = false
        if (progress.value.status === 'completed') {
          ElMessage.success('筛选完成！')
          await loadData()
        } else {
          ElMessage.error('筛选失败: ' + (progress.value.message || ''))
        }
        progress.value = null
      }
    } catch (e) {
      clearInterval(timer)
      running.value = false
    }
  }, 3000)
}

// 加载AI进化建议
const loadAdvice = async () => {
  try {
    const res = await axios.get('/api/weimu/advice')
    advice.value = res.data?.data || null
  } catch (e) {
    console.error('loadAdvice error:', e)
  }
}

// 加载投资工具推荐
const loadTools = async () => {
  loadingTools.value = true
  try {
    const res = await axios.get('/api/weimu/tools')
    tools.value = res.data?.data || null
  } catch (e) {
    console.error('loadTools error:', e)
  } finally {
    loadingTools.value = false
  }
}

// 触发进化
const triggerEvolve = async () => {
  evolving.value = true
  try {
    const res = await axios.post('/api/weimu/evolve')
    ElMessage.success('进化任务已启动，AI正在分析最新政策和行情...')
    // 30秒后刷新建议
    setTimeout(async () => {
      await loadAdvice()
      evolving.value = false
      ElMessage.success('进化完成，建议已更新')
    }, 30000)
  } catch (e) {
    ElMessage.error('触发失败')
    evolving.value = false
  }
}

onMounted(() => {
  loadMarketAnalysis()
  loadAllocation()
  loadAdvice()
  loadTools()
  loadData()
})
</script>
