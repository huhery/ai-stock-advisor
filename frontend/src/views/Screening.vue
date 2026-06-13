<template>
  <div>
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>每日选股推荐</span>
          <div style="display: flex; align-items: center; gap: 12px">
            <el-select v-model="selectedDate" placeholder="选择日期" @change="loadHistory"
              style="width: 160px" clearable>
              <el-option v-for="d in availableDates" :key="d" :label="d" :value="d" />
            </el-select>
            <el-button @click="loadToday" :type="!selectedDate ? 'primary' : ''">今日</el-button>
            <el-button type="primary" @click="triggerRun" :loading="running">手动选股</el-button>
          </div>
        </div>
      </template>

      <el-table :data="stocks" stripe border>
        <el-table-column prop="stock_code" label="代码" width="90" />
        <el-table-column prop="stock_name" label="名称" width="100" />
        <el-table-column prop="sector" label="板块" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.sector" size="small" type="info">{{ row.sector }}</el-tag>
            <span v-else style="color:#ccc">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="total_score" label="评分" width="70">
          <template #default="{ row }">
            <el-tag :type="row.total_score > 100 ? 'danger' : 'warning'" size="small">
              {{ row.total_score }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="买入" width="160">
          <template #default="{ row }">
            <div style="font-size:12px">
              <div><b style="color:#c41d7f">¥{{ row.buy_price }}</b></div>
              <div style="color:#666">{{ row.buy_type }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="止盈/止损" width="130">
          <template #default="{ row }">
            <div style="font-size:12px">
              <div style="color:red">止盈: ¥{{ row.take_profit_price }}</div>
              <div style="color:green">止损: ¥{{ row.stop_loss_price }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="卖出" width="160">
          <template #default="{ row }">
            <div v-if="row.sell_price" style="font-size:12px">
              <div><b>¥{{ row.sell_price }}</b>（{{ row.sell_date }}）</div>
              <div :style="{ color: row.profit_pct > 0 ? 'red' : 'green' }">
                {{ row.profit_pct > 0 ? '+' : '' }}{{ row.profit_pct }}%
              </div>
              <div style="color:#666">{{ row.sell_type }}</div>
            </div>
            <el-tag v-else size="small" type="info">持有中</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="筛选理由" min-width="160" />
      </el-table>

      <el-empty v-if="!stocks.length" description="暂无数据，请点击「手动选股」生成推荐" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getTodayScreening, getHistoryScreening, getScreeningDates, triggerScreening } from '../api'
import { ElMessage } from 'element-plus'

const stocks = ref([])
const selectedDate = ref('')
const availableDates = ref([])
const running = ref(false)

const loadDates = async () => {
  try {
    const res = await getScreeningDates()
    availableDates.value = res.data?.data || []
  } catch (e) { console.error(e) }
}

const loadToday = async () => {
  selectedDate.value = ''
  try {
    const res = await getTodayScreening()
    stocks.value = res.data?.data || []
  } catch (e) { console.error(e) }
}

const loadHistory = async (date) => {
  if (!date) {
    loadToday()
    return
  }
  try {
    const res = await getHistoryScreening(date)
    stocks.value = res.data?.data || []
    if (!stocks.value.length) {
      ElMessage.info('该日期暂无选股记录')
    }
  } catch (e) { console.error(e) }
}

const triggerRun = async () => {
  running.value = true
  try {
    await triggerScreening()
    ElMessage.success('选股任务已启动，请稍候...')
    setTimeout(async () => {
      await loadToday()
      await loadDates()
    }, 5000)
  } catch (e) {
    ElMessage.error('触发失败')
  } finally {
    running.value = false
  }
}

onMounted(() => {
  loadToday()
  loadDates()
})
</script>
