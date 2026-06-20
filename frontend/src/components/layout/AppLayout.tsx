import { type ReactNode } from 'react'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import BottomNav from './BottomNav'

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[#0a0f1e]">
      <Sidebar />
      <TopBar />
      <main className="md:ml-56 pt-14 pb-16 md:pb-0 min-h-screen">
        <div className="max-w-7xl mx-auto px-4 py-6">
          {children}
        </div>
      </main>
      <BottomNav />
    </div>
  )
}
