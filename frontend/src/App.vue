<template>
  <div class="container">
    <h1>UML-Generator</h1>
    <p class="hint">Bitte wählen Sie die gewünschten Parameter aus, um den UML-Generator zu konfigurieren.</p>
    <div class="dropdowns">
      <label>
        Modell:
        <select v-model="param_model">
          <option value="gemini-2.5-flash">gemini-2.5-flash</option>
          <option value="gpt-oss:120b">gpt-oss:120b</option>
        </select>
      </label>
      <label>
        Type of exercise:
        <select v-model="param_ex_type">
          <option value="Text-Exercise">Text-exercise</option>
        </select>
      </label>
      <label>
        Level of difficulty:
        <select v-model="param_dif_level">
          <option value="Beginner">Beginner</option>
          <option value="Intermediate">Intermediate</option>
          <option value="Expert">Expert</option>
        </select>
      </label>
      <label>
        Study goal:
        <select v-model="param_study_goal">
          <option value="Defining attributes that could be a class (ART)">Defining attributes that could be a class (ART)</option>
          <option value="Not considering the problem from an holistic perspective (HOL)">Not considering the problem from an holistic perspective (HOL)</option>
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
      {{ isSubmitting ? "Wird generiert..." : "Aufgabe generieren" }}
    </button>
    <section v-if="result" class="result">
          <h2>Generierte Aufgabe</h2>
          <pre class="json-output">{{ formatTaskJson() }}</pre>
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
      param_model: 'gemini-2.5-flash', // erste Option
      param_ex_type: 'Text-Exercise',  // erste Option
      param_dif_level: 'Beginner',     // erste Option
      param_study_goal: 'Defining attributes that could be a class (ART)', // erste Option
      param_length: 'Short',
      isSubmitting: false,
      result: null,
      error: '',
      promptTemplate:
        'Erstelle eine UML-Aufgabe basierend auf den Parametern: Modell={param_model}, Aufgabentyp={param_ex_type}, Schwierigkeit={param_dif_level}, Lernziel={param_study_goal}, Länge={param_length}. Formuliere die Aufgabe als Liste von Anforderungen.'
    }
  },
  methods: {
    async submitGeneration() {
      this.error = ''
      this.result = null

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
        this.error = 'Bitte alle Parameter auswählen.'
        return
      }

      this.isSubmitting = true
      try {
        const response = await axios.post('/api/generate', {
          parameters,
          prompt_template: this.promptTemplate
        })
        this.result = response.data
      } catch (err) {
        this.error = err.response?.data?.error || 'Fehler bei der Generierung.'
      } finally {
        this.isSubmitting = false
      }
    },

    formatTaskJson() {
      try {
        const obj = typeof this.result.task === 'string'
          ? JSON.parse(this.result.task)
          : this.result.task
        return JSON.stringify(obj, null, 2)
      } catch (e) {
        return this.result.task
      }
    }
  }
}
</script>

<!-- Globale Styles werden jetzt in src/assets/global.css verwaltet -->

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
</style>
