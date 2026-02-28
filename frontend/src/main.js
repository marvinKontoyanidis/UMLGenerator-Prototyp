import { createApp } from 'vue'
import App from './App.vue'
import './assets/global.css'

// Create and mount the single-page Vue application that renders ``App.vue``
const app = createApp(App)
app.mount('#app')
