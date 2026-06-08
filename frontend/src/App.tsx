import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Analytics from './pages/Analytics'
import Overview from './pages/Overview'
import Produce from './pages/Produce'
import Reconciliation from './pages/Reconciliation'
import Transactions from './pages/Transactions'

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-slate-50 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/transactions" element={<Transactions />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/reconciliation" element={<Reconciliation />} />
            <Route path="/produce"        element={<Produce />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
