import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import AuctionRoom from './pages/AuctionRoom';
import AdminDashboard from './pages/AdminDashboard';
import LeaderboardPage from './pages/Leaderboard';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-slate-950 text-slate-200 selection:bg-indigo-500/30 font-sans pb-20 md:pb-0">
        <Navbar />
        <div className="animate-in fade-in duration-500">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/auction" element={<AuctionRoom />} />
            <Route path="/admin" element={<AdminDashboard />} />
            <Route path="/leaderboard" element={<LeaderboardPage />} />
          </Routes>
        </div>
      </div>
    </Router>
  );
}

export default App;
