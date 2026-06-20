import { Routes, Route } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import DashboardPage from './pages/DashboardPage'
import WatchlistPage from './pages/WatchlistPage'
import PortfolioPage from './pages/PortfolioPage'
import TradesPage from './pages/TradesPage'
import NewsPage from './pages/NewsPage'
import FiiDiiPage from './pages/FiiDiiPage'
import TaxPage from './pages/TaxPage'
import AgentRunsPage from './pages/AgentRunsPage'

export default function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/watchlist" element={<WatchlistPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/trades" element={<TradesPage />} />
        <Route path="/news" element={<NewsPage />} />
        <Route path="/fii-dii" element={<FiiDiiPage />} />
        <Route path="/tax" element={<TaxPage />} />
        <Route path="/runs" element={<AgentRunsPage />} />
        <Route path="*" element={<DashboardPage />} />
      </Routes>
    </AppLayout>
  )
}
