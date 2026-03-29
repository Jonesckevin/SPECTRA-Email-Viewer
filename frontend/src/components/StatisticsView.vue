<template>
  <div class="h-full overflow-y-auto bg-gray-50 dark:bg-gray-950 p-6">
    <!-- Loading skeleton -->
    <div v-if="loading" class="max-w-6xl mx-auto space-y-6">
      <!-- Skeleton overview cards -->
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <div v-for="i in 6" :key="i" class="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 shadow-sm animate-pulse">
          <div class="flex items-center gap-2 mb-2">
            <div class="w-6 h-6 bg-gray-200 dark:bg-gray-700 rounded"></div>
            <div class="h-3 bg-gray-200 dark:bg-gray-700 rounded w-16"></div>
          </div>
          <div class="h-6 bg-gray-200 dark:bg-gray-700 rounded w-12"></div>
        </div>
      </div>
      <!-- Skeleton chart cards -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div v-for="i in 4" :key="i" class="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
          <div class="px-4 py-3 border-b border-gray-100 dark:border-gray-700 animate-pulse">
            <div class="h-4 bg-gray-200 dark:bg-gray-700 rounded w-32"></div>
          </div>
          <div class="p-4 space-y-3 animate-pulse">
            <div v-for="j in 5" :key="j" class="flex items-center gap-2">
              <div class="h-3 bg-gray-200 dark:bg-gray-700 rounded w-24"></div>
              <div class="flex-1 h-5 bg-gray-100 dark:bg-gray-700 rounded-full"></div>
              <div class="h-3 bg-gray-200 dark:bg-gray-700 rounded w-8"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="flex items-center justify-center h-64">
      <div class="text-red-500 dark:text-red-400">{{ error }}</div>
    </div>

    <!-- Statistics content -->
    <div v-else-if="data" class="max-w-6xl mx-auto space-y-6">

      <!-- Overview cards -->
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <StatCard label="Total Emails" :value="data.overview.total_emails" icon="📧" />
        <StatCard label="Starred" :value="data.overview.starred" icon="⭐" />
        <StatCard label="With Attachments" :value="data.overview.with_attachments" icon="📎" />
        <StatCard label="Total Attachments" :value="data.overview.total_attachments" icon="📁" />
        <StatCard label="Avg Body Size" :value="formatBytes(data.overview.avg_body_size)" icon="📏" />
        <StatCard label="Date Range" :value="dateRangeLabel" icon="📅" small />
      </div>

      <!-- Charts row 1 -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Top Senders -->
        <ChartCard title="Top 10 Senders">
          <BarChart
            :items="data.top_senders.map(s => ({ label: s.sender_name || s.sender, value: s.count }))"
            color="blue"
          />
        </ChartCard>

        <!-- Top Domains -->
        <ChartCard title="Top 10 Sender Domains">
          <BarChart
            :items="data.top_domains.map(d => ({ label: d.domain, value: d.count }))"
            color="indigo"
          />
        </ChartCard>
      </div>

      <!-- Charts row 2 -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Top Recipients -->
        <ChartCard title="Top 10 Recipients">
          <BarChart
            :items="data.top_recipients.map(r => ({ label: truncate(r.recipient, 40), value: r.count }))"
            color="emerald"
          />
        </ChartCard>

        <!-- Top Attachment Types -->
        <ChartCard title="Top Attachment Types">
          <BarChart
            :items="data.top_attachment_types.map(t => ({ label: t.content_type, value: t.count }))"
            color="amber"
          />
        </ChartCard>
      </div>

      <!-- Charts row 3 -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Emails by Day of Week -->
        <ChartCard title="Emails by Day of Week">
          <BarChart
            :items="data.emails_by_day.map(d => ({ label: d.day.slice(0, 3), value: d.count }))"
            color="rose"
          />
        </ChartCard>

        <!-- Emails by Hour -->
        <ChartCard title="Emails by Hour of Day">
          <BarChart
            :items="data.emails_by_hour.map(h => ({ label: h.hour + ':00', value: h.count }))"
            color="cyan"
          />
        </ChartCard>
      </div>

      <!-- Timeline chart (full width) -->
      <ChartCard title="Emails Over Time (Monthly)" v-if="data.emails_by_month.length">
        <TimelineChart :items="data.emails_by_month" />
      </ChartCard>

      <!-- File Sources -->
      <ChartCard title="Import Sources" v-if="data.top_sources.length">
        <BarChart
          :items="data.top_sources.map(s => ({ label: s.source, value: s.count }))"
          color="violet"
        />
      </ChartCard>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { fetchStatistics } from '../api'

const data = ref(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    data.value = await fetchStatistics()
  } catch (e) {
    error.value = e.message || 'Failed to load statistics'
  } finally {
    loading.value = false
  }
})

const dateRangeLabel = computed(() => {
  if (!data.value?.overview?.date_range) return '—'
  const { earliest, latest } = data.value.overview.date_range
  if (!earliest) return '—'
  const e = earliest.split(' ')[0] || earliest.slice(0, 10)
  const l = (latest || earliest).split(' ')[0] || (latest || earliest).slice(0, 10)
  return `${e} — ${l}`
})

function formatBytes(n) {
  if (!n) return '0 B'
  if (n < 1024) return n + ' B'
  if (n < 1048576) return (n / 1024).toFixed(1) + ' KB'
  return (n / 1048576).toFixed(1) + ' MB'
}

function truncate(str, max) {
  if (!str) return '(unknown)'
  return str.length > max ? str.slice(0, max) + '…' : str
}

// --- Sub-components defined inline ---

const StatCard = {
  props: { label: String, value: [String, Number], icon: String, small: Boolean },
  setup(props) {
    return () => h('div', {
      class: 'bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 shadow-sm'
    }, [
      h('div', { class: 'flex items-center gap-2 mb-1' }, [
        h('span', { class: 'text-lg' }, props.icon),
        h('span', { class: 'text-xs text-gray-500 dark:text-gray-400 font-medium' }, props.label),
      ]),
      h('div', {
        class: [
          'font-bold text-gray-900 dark:text-gray-100',
          props.small ? 'text-xs leading-tight' : 'text-xl'
        ].join(' ')
      }, typeof props.value === 'number' ? props.value.toLocaleString() : props.value),
    ])
  }
}

const ChartCard = {
  props: { title: String },
  setup(props, { slots }) {
    return () => h('div', {
      class: 'bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm'
    }, [
      h('div', {
        class: 'px-4 py-3 border-b border-gray-100 dark:border-gray-700 font-medium text-sm text-gray-700 dark:text-gray-300'
      }, props.title),
      h('div', { class: 'p-4' }, slots.default?.()),
    ])
  }
}

const colorMap = {
  blue: { bar: 'bg-blue-500 dark:bg-blue-400', text: 'text-blue-600 dark:text-blue-400' },
  indigo: { bar: 'bg-indigo-500 dark:bg-indigo-400', text: 'text-indigo-600 dark:text-indigo-400' },
  emerald: { bar: 'bg-emerald-500 dark:bg-emerald-400', text: 'text-emerald-600 dark:text-emerald-400' },
  amber: { bar: 'bg-amber-500 dark:bg-amber-400', text: 'text-amber-600 dark:text-amber-400' },
  rose: { bar: 'bg-rose-500 dark:bg-rose-400', text: 'text-rose-600 dark:text-rose-400' },
  cyan: { bar: 'bg-cyan-500 dark:bg-cyan-400', text: 'text-cyan-600 dark:text-cyan-400' },
  violet: { bar: 'bg-violet-500 dark:bg-violet-400', text: 'text-violet-600 dark:text-violet-400' },
}

const BarChart = {
  props: {
    items: Array,
    color: { type: String, default: 'blue' },
  },
  setup(props) {
    return () => {
      if (!props.items?.length) {
        return h('div', { class: 'text-gray-400 dark:text-gray-500 text-sm text-center py-4' }, 'No data')
      }
      const max = Math.max(...props.items.map(i => i.value), 1)
      const c = colorMap[props.color] || colorMap.blue
      return h('div', { class: 'space-y-2' }, props.items.map(item =>
        h('div', { class: 'flex items-center gap-2' }, [
          h('div', {
            class: 'text-xs text-gray-600 dark:text-gray-400 w-32 shrink-0 truncate text-right',
            title: item.label,
          }, item.label),
          h('div', { class: 'flex-1 bg-gray-100 dark:bg-gray-700 rounded-full h-5 overflow-hidden' }, [
            h('div', {
              class: `${c.bar} h-full rounded-full transition-all duration-500 ease-out flex items-center justify-end px-1.5`,
              style: { width: Math.max((item.value / max) * 100, 2) + '%' },
            }, [
              h('span', { class: 'text-[10px] text-white font-bold' },
                item.value >= max * 0.1 ? item.value.toLocaleString() : '')
            ]),
          ]),
          h('span', {
            class: `text-xs font-medium ${c.text} w-12 text-right shrink-0`,
          }, item.value.toLocaleString()),
        ])
      ))
    }
  }
}

const TimelineChart = {
  props: { items: Array },
  setup(props) {
    return () => {
      if (!props.items?.length) return h('div', { class: 'text-gray-400 text-sm text-center py-4' }, 'No data')

      const max = Math.max(...props.items.map(i => i.count), 1)
      const barWidth = Math.max(100 / props.items.length, 0.5)

      return h('div', { class: 'overflow-x-auto' }, [
        h('div', {
          class: 'flex items-end gap-px',
          style: { minWidth: Math.max(props.items.length * 20, 300) + 'px', height: '160px' },
        }, props.items.map(item =>
          h('div', {
            class: 'flex flex-col items-center flex-1 group relative',
            style: { minWidth: '16px' },
          }, [
            // Tooltip
            h('div', {
              class: 'absolute bottom-full mb-1 bg-gray-800 dark:bg-gray-200 text-white dark:text-gray-900 text-[10px] px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-10 transition-opacity',
            }, `${item.month}: ${item.count.toLocaleString()}`),
            // Bar
            h('div', {
              class: 'w-full bg-blue-500 dark:bg-blue-400 rounded-t transition-all hover:bg-blue-600 dark:hover:bg-blue-300',
              style: { height: Math.max((item.count / max) * 140, 2) + 'px' },
            }),
            // Label (shown every Nth item)
            props.items.length <= 24 || props.items.indexOf(item) % Math.ceil(props.items.length / 12) === 0
              ? h('div', { class: 'text-[9px] text-gray-400 dark:text-gray-500 mt-1 -rotate-45 origin-top-left whitespace-nowrap' }, item.month)
              : null,
          ])
        )),
      ])
    }
  }
}
</script>
