import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from '@/components/layout/Layout'
import Home from '@/pages/Home'
import Arena from '@/pages/Arena'
import AgentProfile from '@/pages/AgentProfile'
import Betting from '@/pages/Betting'
import Dashboard from '@/pages/Dashboard'
import Admin from '@/pages/Admin'
import Login from '@/pages/Login'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="arena" element={<Arena />} />
          <Route path="agents/:agentId" element={<AgentProfile />} />
          <Route path="bet" element={<Betting />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="admin" element={<Admin />} />
        </Route>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
