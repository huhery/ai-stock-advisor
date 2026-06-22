<template>
  <div>
    <el-row :gutter="20" style="margin-bottom: 20px">
      <el-col :span="8">
        <el-card>
          <el-statistic title="整体胜率 (T+5)" :value="winRate" suffix="%" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <el-statistic title="平均收益 (T+5)" :value="avgChange" suffix="%" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <el-statistic title="总推荐数" :value="totalCount" />
        </el-card>
      </el-col>
    </el-row>

    <el-card header="各周期表现">
      <el-table :data="byDays" stripe>
        <el-table-column prop="days_after" label="周期" width="100">
          <template #default="{ row }">T+{{ row.days_after }}</template>
        </el-table-column>
        <el-table-column prop="total" label="样本数" width="100" />
        <el-table-column label="胜率" width="120">
          <template #default="{ row }">
            {{ row.total > 0 ? (row.win_count / row.total * 100).toFixed(1) : 0 }}%
          </template>
        </el-table-column>
        <el-table-column label="平均收益" width="120">
          <template #default="{ row }">
            <span :style="{ color: row.avg_change > 0 ? 'red' : 'green' }">
              {{ row.avg_change ? row.avg_change.toFixed(2) : 0 }}%
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getPerformance } from '../api'

const winRate = ref(0)
const avgChange = ref(0)
const totalCount = ref(0)
const byDays = ref([])

// 把可能为字符串/Decimal 的值安全转为数字
const toNum = (v) => {
  const n = Number(v)
  return isNaN(n) ? 0 : n
}

onMounted(async () => {
  try {
    const res = await getPerformance()
    // 兼容多层包装：Java 后端用 Result 再包一层 -> {code,data:{code,data:{...}}}
    let data = res.data?.data || {}
    if (data && data.code !== undefined && data.data !== undefined) {
      data = data.data
    }

    winRate.value = toNum(data.overall_win_rate)
    avgChange.value = toNum(data.t5_stats?.avg_change).toFixed(2)
    totalCount.value = toNum(data.t5_stats?.total)
    // 各周期数值统一转为数字，避免字符串导致显示异常
    byDays.value = (data.by_days || []).map(d => ({
      days_after: toNum(d.days_after),
      total: toNum(d.total),
      win_count: toNum(d.win_count),
      avg_change: toNum(d.avg_change),
    }))
  } catch (e) { console.error(e) }
})
</script>
