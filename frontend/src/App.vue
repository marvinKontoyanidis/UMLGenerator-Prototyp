<template>
  <div class="container">
    <h1>UML Generator</h1>
    <p class="hint">Please select the desired parameters to configure the UML generator.</p>
    <div class="dropdowns">
      <label>
        Model:
        <select v-model="param_model">
          <option value="gemini-2.5-flash">gemini-2.5-flash</option>
          <option value="gpt-5.1-chat-latest">gpt-5.1-chat-latest</option>
          <option value="gpt-oss:120b">gpt-oss:120b</option>
        </select>
      </label>
      <label>
        Type of UML:
        <select v-model="param_ex_type">
          <option value="Class diagram">Class diagramm</option>
        </select>
      </label>
      <label>
        Level of difficulty:
        <select v-model="param_dif_level">
          <option value="Easy">Beginner</option>
          <option value="Medium">Intermediate</option>
          <option value="Hard">Expert</option>
        </select>
      </label>
      <label>
        Study goal:
        <select v-model="param_study_goal">
          <option value="ATR">Defining attributes that could be a class (ATR)</option>
          <option value="HOL">Not considering the problem from a holistic perspective (HOL)</option>
          <option value="LIS">Incorrect use of multiplicity between classes (LIS)</option>
          <option value="COM">Classes with inadequate or insufficient behavior (COM)</option>
        </select>
      </label>
      <label>
        Length of exercise:
        <select v-model="param_length">
          <option value="Short">Short</option>
          <option value="Medium">Medium</option>
          <option value="Long">Long</option>
        </select>
      </label>
    </div>
    <label class="prompt-template">

    </label>

    <label class="toggle-eval">
      <input type="checkbox" v-model="evaluate" />
      Evaluate generated exercise with a second LLM
    </label>

    <button :disabled="isSubmitting" @click="submitGeneration">
      {{ isSubmitting ? "Generating..." : "Generate exercise" }}
    </button>

    <!-- Structured display of the LLM task -->
    <section v-if="parsedTask" class="result">
      <h2>{{ parsedTask.title }}</h2>

      <h3>Learning objectives</h3>
      <ul>
        <li v-for="(obj, idx) in parsedTask.learning_objectives" :key="idx">
          {{ obj }}
        </li>
      </ul>

      <h3>Problem description</h3>
      <p class="problem-description">
        {{ parsedTask.problem_description }}
      </p>

      <h3>Selected parameters / Metadata</h3>
      <ul class="metadata">
        <li>Difficulty level: {{ parsedTask.metadata.difficulty_level }}</li>
        <li>Length: {{ parsedTask.metadata.length }}</li>
        <li>Study goal: {{ parsedTask.metadata.study_goal_id }}</li>
        <li>Diagram type: {{ parsedTask.metadata.diagram_type }}</li>
      </ul>

      <section v-if="evaluation" class="evaluation">
        <h3>Automatic evaluation scores</h3>

        <!-- Overall total score -->
        <p class="overall-score" v-if="evaluation.fullScore != null">
          Overall quality score: <strong>{{ evaluation.fullScore.toFixed(2) }}</strong> / 10
        </p>

        <!-- Dimension aggregates -->
        <h4>Dimension scores</h4>
        <table class="scores-table dim-table">
          <thead>
            <tr>
              <th>Dimension</th>
              <th>Code</th>
              <th>Score (0–2)</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="dim in dimensionRows" :key="dim.code">
              <td>{{ dim.label }}</td>
              <td>{{ dim.code }}</td>
              <td>{{ dim.score != null ? dim.score.toFixed(2) : '-' }}</td>
            </tr>
          </tbody>
        </table>

        <!-- Per-item scores with justifications -->
        <h4>Item scores and justifications</h4>
        <table class="scores-table item-table">
          <thead>
            <tr>
              <th>Dimension</th>
              <th>Item</th>
              <th>Score</th>
              <th>Justification</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in itemRows" :key="`${row.dimension}-${row.item}`">
              <td>{{ row.dimensionLabel }}</td>
              <td>{{ row.item }}</td>
              <td>{{ row.score != null ? row.score : '-' }}</td>
              <td>{{ row.justification || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </section>

    <!-- Fallback: if parsing fails, show raw response -->
    <section v-else-if="result" class="result">
      <h2>Raw response</h2>
      <pre class="json-output">{{ result.response }}</pre>
    </section>

    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<script>
import axios from 'axios'

export default {
  name: 'App',
  data() {
    return {
      param_model: 'gemini-2.5-flash',
      param_ex_type: 'Class diagram',
      param_dif_level: 'Easy',
      param_study_goal: 'LIS',
      param_length: 'Short',
      evaluate: true,
      isSubmitting: false,
      result: null,
      parsedTask: null,
      evaluation: null,
      error: ''
    }
  },
  computed: {
    dimensionRows() {
      if (!this.evaluation) return []
      return [
        { code: 'T', label: 'Exercise adherence', score: this.evaluation.dimensions.T },
        { code: 'D', label: 'Difficulty profile adherence', score: this.evaluation.dimensions.D },
        { code: 'S', label: 'Study goal alignment', score: this.evaluation.dimensions.S },
        { code: 'L', label: 'Length adherence', score: this.evaluation.dimensions.L },
        { code: 'P', label: 'Pedagogical quality', score: this.evaluation.dimensions.P }
      ]
    },
    itemRows() {
      if (!this.evaluation) return []
      const rows = []
      const dimLabels = {
        T: 'Exercise adherence',
        D: 'Difficulty profile adherence',
        S: 'Study goal alignment',
        L: 'Length adherence',
        P: 'Pedagogical quality'
      }
      const itemToDim = {
        T1: 'T', T2: 'T',
        D1: 'D', D2: 'D', D3: 'D', D4: 'D',
        S1: 'S', S2: 'S', S3: 'S',
        L1: 'L', L2: 'L',
        P1: 'P', P2: 'P', P3: 'P', P4: 'P'
      }
      const items = this.evaluation.items || {}
      const justs = this.evaluation.justifications || {}
      for (const [item, score] of Object.entries(items)) {
        const dim = itemToDim[item]
        rows.push({
          dimension: dim,
          dimensionLabel: dimLabels[dim] || dim,
          item,
          score,
          justification: justs[item]
        })
      }
      return rows
    }
  },
  methods: {
    async submitGeneration() {
      this.error = ''
      this.result = null
      this.parsedTask = null
      this.evaluation = null

      const parameters = {
        param_model: this.param_model,
        param_ex_type: this.param_ex_type,
        param_dif_level: this.param_dif_level,
        param_study_goal: this.param_study_goal,
        param_length: this.param_length
      }

      if (
        !parameters.param_model ||
        !parameters.param_ex_type ||
        !parameters.param_dif_level ||
        !parameters.param_study_goal ||
        !parameters.param_length
      ) {
        this.error = 'Please select all parameters.'
        return
      }

      this.isSubmitting = true
      try {
        const response = await axios.post('/api/generate', { parameters, evaluate: this.evaluate })
        this.result = response.data

        const raw = this.result.response

        if (!raw) {
          this.parsedTask = null
          console.error('No response from backend received')
          return
        }

        if (typeof raw === 'string') {
          const cleaned = raw.replace(/^```[a-zA-Z]*\n?/, '').replace(/```$/, '')
          try {
            this.parsedTask = JSON.parse(cleaned)
          } catch (e) {
            this.parsedTask = null
            console.error('Error parsing LLM response string:', e, cleaned)
          }
        } else if (typeof raw === 'object') {
          this.parsedTask = raw
        } else {
          this.parsedTask = null
          console.error('Unexpected type for result.response:', typeof raw, raw)
        }

        // Extract evaluation details (if backend provides them)
        if (this.result.evaluation_scores && typeof this.result.evaluation_scores === 'object') {
          const scores = this.result.evaluation_scores
          // Legacy simple map
          this.evaluationScores = scores
        }

        // New structured evaluation object if backend is extended:
        // Expecting shape similar to:
        // {
        //   items: { T1: number, ... },
        //   dimensions: { T: number, D: number, ... },
        //   fullScore: number,
        //   justifications: { T1: string, ... }
        // }
        if (this.result.evaluation && typeof this.result.evaluation === 'object') {
          this.evaluation = {
            items: this.result.evaluation.items || {},
            dimensions: this.result.evaluation.dimensions || {},
            fullScore: this.result.evaluation.fullScore ?? null,
            justifications: this.result.evaluation.justifications || {}
          }
        }
      } catch (err) {
        this.error = err.response?.data?.error || 'Error during generation.'
      } finally {
        this.isSubmitting = false
      }
    }
  }
}
</script>

<!-- Global styles are managed in src/assets/global.css -->

<style scoped>
.container {
  max-width: 640px;
  margin: 0 auto;
  padding: 24px;
  text-align: center;
}
.hint {
  margin-bottom: 16px;
  color: #4b5563;
}
.dropdowns {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}
.dropdowns label {
  min-width: 0;
}
.dropdowns select {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.prompt-template {
  display: block;
  margin-top: 16px;
}
.toggle-eval {
  display: block;
  margin-top: 12px;
  text-align: left;
}
textarea {
  width: 100%;
  margin-top: 8px;
  padding: 10px;
  border-radius: 8px;
  border: 1px solid #ccc;
  font-family: inherit;
}
button {
  margin-top: 16px;
  padding: 10px 16px;
  border: none;
  background-color: #3b82f6;
  color: white;
  border-radius: 8px;
  cursor: pointer;
}
button:disabled {
  background-color: #93c5fd;
  cursor: not-allowed;
}
.result {
  margin-top: 24px;
  text-align: left;
}
.error {
  margin-top: 12px;
  color: #dc2626;
}

.json-output {
  text-align: left;
  white-space: pre-wrap;
  word-wrap: break-word;
  overflow-x: auto;
  max-width: 100%;
  max-height: 400px;
}
.problem-description {
  white-space: pre-wrap;
}
.metadata {
  list-style: none;
  padding-left: 0;
}
.evaluation {
  margin-top: 16px;
}
.scores-table {
  width: 100%;
  border-collapse: collapse;
}
.scores-table th,
.scores-table td {
  border: 1px solid #e5e7eb;
  padding: 4px 8px;
  text-align: left;
}
.overall-score {
  margin-bottom: 12px;
}
.dim-table {
  margin-bottom: 16px;
}
.item-table td:nth-child(4) {
  max-width: 300px;
  white-space: pre-wrap;
}
</style>
