<template>
  <div class="container">
    <h1>UML-Generator</h1>
    <p class="hint">Bitte wählen Sie die gewünschten Parameter aus, um den UML-Generator zu konfigurieren.</p>
    <div class="dropdowns">
      <label>
        Parameter 1:
        <select v-model="param1">
          <option value="">Bitte wählen</option>
          <option value="A">A</option>
          <option value="B">B</option>
          <option value="C">C</option>
        </select>
      </label>
      <label>
        Parameter 2:
        <select v-model="param2">
          <option value="">Bitte wählen</option>
          <option value="X">X</option>
          <option value="Y">Y</option>
          <option value="Z">Z</option>
        </select>
      </label>
      <label>
        Parameter 3:
        <select v-model="param3">
          <option value="">Bitte wählen</option>
          <option value="1">1</option>
          <option value="2">2</option>
          <option value="3">3</option>
        </select>
      </label>
    </div>
    <label class="prompt-template">
      Prompt-Vorlage:
      <textarea
        v-model="promptTemplate"
        rows="5"
        placeholder="Beschreibe hier die Aufgabe. Du kannst {param1}, {param2}, {param3} verwenden."
      ></textarea>
    </label>
    <button :disabled="isSubmitting" @click="submitGeneration">
      {{ isSubmitting ? "Wird generiert..." : "Aufgabe generieren" }}
    </button>
    <section v-if="result" class="result">
      <h2>Generierte Aufgabe</h2>
      <pre>{{ result.task }}</pre>
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
      param1: '',
      param2: '',
      param3: '',
      isSubmitting: false,
      result: null,
      error: '',
      promptTemplate:
        'Erstelle eine UML-Aufgabe, die sich auf {param1}, {param2} und {param3} bezieht. Beschreibe sie als Liste von Anforderungen.'
    }
  },
  methods: {
    async submitGeneration() {
      this.error = ''
      this.result = null
      const parameters = {
        param1: this.param1,
        param2: this.param2,
        param3: this.param3
      }
      if (!parameters.param1 || !parameters.param2 || !parameters.param3) {
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
</style>
