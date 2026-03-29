<template>
  <div class="flex flex-1 overflow-hidden h-full">
    <!-- Email list panel -->
    <div class="w-full md:w-2/5 lg:w-1/3 border-r border-gray-200 dark:border-gray-700 flex flex-col bg-white dark:bg-gray-900"
         :class="{ 'hidden md:flex': selectedEmail }">
      <EmailList
        :emails="emails"
        :selected-id="selectedEmail?.id"
        :loading="loading"
        :total="totalEmails"
        :page="page"
        :per-page="perPage"
        @select="$emit('select', $event)"
        @toggle-star="$emit('toggle-star', $event)"
        @page-change="$emit('page-change', $event)"
      />
    </div>

    <!-- Email detail panel -->
    <div class="flex-1 flex flex-col bg-gray-50 dark:bg-gray-950"
         :class="{ 'hidden md:flex': !selectedEmail }">
      <EmailView
        v-if="selectedEmail"
        :email="selectedEmail"
        @back="$emit('select', null)"
        @toggle-star="$emit('toggle-star-detail', $event)"
      />
      <div v-else class="flex-1 flex items-center justify-center text-gray-400 dark:text-gray-600">
        <div class="text-center">
          <div class="text-5xl mb-4">📬</div>
          <p class="text-lg">Select an email to view</p>
          <p class="text-sm mt-1">Or upload email files to get started</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import EmailList from '../components/EmailList.vue'
import EmailView from '../components/EmailView.vue'

defineProps({
  emails: { type: Array, default: () => [] },
  selectedEmail: { type: Object, default: null },
  loading: Boolean,
  totalEmails: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  perPage: { type: Number, default: 50 },
})

defineEmits(['select', 'toggle-star', 'toggle-star-detail', 'page-change'])
</script>
