import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'

import Stream from './components/stream'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="app">
      <Stream />
    </div>
  )
}

export default App
