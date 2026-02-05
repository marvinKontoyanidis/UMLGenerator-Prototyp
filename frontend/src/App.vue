<template>
  <div class="container">
    <h1>UML Generator</h1>
    <p class="hint">Please select the desired parameters to configure the UML generator.</p>
    <div class="dropdowns">
      <label>
        Model:
        <select v-model="param_model">
          <option value="gemini-2.5-flash">gemini-2.5-flash</option>
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
          <option value="ART">Defining attributes that could be a class (ART)</option>
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
      isSubmitting: false,
      result: null,
      parsedTask: null,
      error: ''
    }
  },
  methods: {
    async submitGeneration() {
      this.error = ''
      this.result = null
      this.parsedTask = null

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
        const response = await axios.post('/api/generate', { parameters })
        this.result = response.data

        const raw = this.result.response

        if (!raw) {
          this.parsedTask = null
          console.error('No response from backend received')
          return
        }

        if (typeof raw === 'string') {
          // If the string is wrapped in ``` ... ```, remove those backticks
          const cleaned = raw.replace(/^```[a-zA-Z]*\n?/, '').replace(/```$/, '')
          try {
            this.parsedTask = JSON.parse(cleaned)
          } catch (e) {
            this.parsedTask = null
            console.error('Error parsing LLM response string:', e, cleaned)
          }
        } else if (typeof raw === 'object') {
          // Already provided as an object
          this.parsedTask = raw
        } else {
          this.parsedTask = null
          console.error('Unexpected type for result.response:', typeof raw, raw)
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
</style>
