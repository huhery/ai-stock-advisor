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

onMounted(async () => {
  try {
    const res = await getPerformance()
    const data = res.data?.data || {}
    winRate.value = data.overall_win_rate || 0
    avgChange.value = data.t5_stats?.avg_change?.toFixed(2) || 0
    totalCount.value = data.t5_stats?.total || 0
    byDays.value = data.by_days || []
  } catch (e) { console.error(e) }
})
</script>
