<template>
  <div class="fixed inset-0 bg-black/40 z-50 flex items-start justify-center pt-20" @click.self="$emit('close')">
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-2xl max-h-[70vh] overflow-y-auto mx-4">
      <div class="sticky top-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between">
        <h2 class="text-lg font-bold text-gray-800 dark:text-gray-100">Search Help</h2>
        <button @click="$emit('close')" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl">&times;</button>
      </div>

      <div class="px-6 py-4 space-y-6 text-sm">
        <!-- Basic search -->
        <section>
          <h3 class="font-semibold text-gray-700 dark:text-gray-200 mb-2">Basic Search</h3>
          <p class="text-gray-500 dark:text-gray-400 mb-2">Just type words to search across all fields (subject, sender, body).</p>
          <div class="space-y-1">
            <ExampleRow example="meeting notes" @click="insert('meeting notes')" />
            <ExampleRow :example="phraseExample" @click="insert(phraseExample)" />
          </div>
        </section>

        <!-- Field operators -->
        <section>
          <h3 class="font-semibold text-gray-700 dark:text-gray-200 mb-2">Field Operators</h3>
          <table class="w-full text-left">
            <tbody>
              <tr v-for="op in fieldOps" :key="op.field" class="border-b border-gray-100 dark:border-gray-700">
                <td class="py-1.5 pr-3 font-mono text-blue-600 dark:text-blue-400 whitespace-nowrap">{{ op.field }}</td>
                <td class="py-1.5 pr-3 text-gray-500 dark:text-gray-400">{{ op.desc }}</td>
                <td class="py-1.5">
                  <button @click="insert(op.example)" class="text-blue-500 dark:text-blue-400 hover:underline font-mono text-xs">
                    {{ op.example }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- Boolean operators -->
        <section>
          <h3 class="font-semibold text-gray-700 dark:text-gray-200 mb-2">Boolean Operators</h3>
          <table class="w-full text-left">
            <tbody>
              <tr v-for="op in boolOps" :key="op.op" class="border-b border-gray-100 dark:border-gray-700">
                <td class="py-1.5 pr-3 font-mono text-purple-600 dark:text-purple-400 font-bold whitespace-nowrap">{{ op.op }}</td>
                <td class="py-1.5 pr-3 text-gray-500 dark:text-gray-400">{{ op.desc }}</td>
                <td class="py-1.5">
                  <button @click="insert(op.example)" class="text-blue-500 dark:text-blue-400 hover:underline font-mono text-xs">
                    {{ op.example }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- Date filters -->
        <section>
          <h3 class="font-semibold text-gray-700 dark:text-gray-200 mb-2">Date Filters</h3>
          <div class="space-y-1">
            <ExampleRow example="after:2024-01-01" label="Emails after date" @click="insert('after:2024-01-01')" />
            <ExampleRow example="before:2024-12-31" label="Emails before date" @click="insert('before:2024-12-31')" />
            <ExampleRow example="date:2024-06-15" label="Emails on exact date" @click="insert('date:2024-06-15')" />
            <ExampleRow example="after:2024-01-01 before:2024-06-30" label="Date range" @click="insert('after:2024-01-01 before:2024-06-30')" />
          </div>
        </section>

        <!-- Status filters -->
        <section>
          <h3 class="font-semibold text-gray-700 dark:text-gray-200 mb-2">Status Filters</h3>
          <div class="space-y-1">
            <ExampleRow example="is:starred" label="Only starred emails" @click="insert('is:starred')" />
            <ExampleRow example="has:attachment" label="Emails with attachments" @click="insert('has:attachment')" />
          </div>
        </section>

        <!-- Regex -->
        <section>
          <h3 class="font-semibold text-gray-700 dark:text-gray-200 mb-2">Regex Search</h3>
          <p class="text-gray-500 dark:text-gray-400 mb-2">Use <code class="bg-gray-100 dark:bg-gray-700 px-1 rounded">regex:/pattern/</code> for regular expression matching.</p>
          <div class="space-y-1">
            <ExampleRow v-for="rx in regexExamples" :key="rx.example" :example="rx.example" :label="rx.label" @click="insert(rx.example)" />
          </div>
        </section>

        <!-- Complex examples -->
        <section>
          <h3 class="font-semibold text-gray-700 dark:text-gray-200 mb-2">Complex Examples</h3>
          <div class="space-y-1">
            <ExampleRow v-for="cx in complexExamples" :key="cx" :example="cx" @click="insert(cx)" />
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import ExampleRow from './ExampleRow.vue'

const emit = defineEmits(['close', 'insert'])

function insert(text) {
  emit('insert', text)
}

const phraseExample = '"exact phrase match"'

const regexExamples = [
  { example: 'regex:/invoice-\\d+/', label: 'Match invoice numbers' },
  { example: 'regex:/\\b[A-Z]{2,5}-\\d+\\b/', label: 'Match ticket IDs like PROJ-123' },
]

const complexExamples = [
  'from:boss@company.com AND subject:urgent',
  '(from:alice OR from:bob) AND has:attachment',
  'subject:report after:2024-01-01 -from:spam@',
  'is:starred AND has:attachment AND after:2024-06-01',
]

const fieldOps = [
  { field: 'from:', desc: 'Sender email/name', example: 'from:john@example.com' },
  { field: 'to:', desc: 'Recipient', example: 'to:team@company.com' },
  { field: 'subject:', desc: 'Subject line', example: 'subject:"quarterly report"' },
  { field: 'body:', desc: 'Message body', example: 'body:deadline' },
  { field: 'filename:', desc: 'Attachment filename', example: 'filename:invoice.pdf' },
  { field: 'cc:', desc: 'CC recipient', example: 'cc:manager@company.com' },
  { field: 'bcc:', desc: 'BCC recipient', example: 'bcc:hidden@company.com' },
]

const boolOps = [
  { op: 'AND', desc: 'Both terms must match', example: 'budget AND forecast' },
  { op: 'OR', desc: 'Either term matches', example: 'meeting OR conference' },
  { op: 'NOT', desc: 'Exclude term', example: 'report NOT draft' },
  { op: '- (minus)', desc: 'Exclude (shorthand)', example: 'invoice -cancelled' },
  { op: '( )', desc: 'Group expressions', example: '(urgent OR important) AND from:boss' },
  { op: '" "', desc: 'Exact phrase', example: '"project deadline"' },
]
</script>
