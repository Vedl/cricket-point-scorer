import { useState } from 'react';
import { HeroInput } from './components/HeroInput';
import { PlayerCard, Player } from './components/PlayerCard';
import { Trophy } from 'lucide-react';

function App() {
  const [loading, setLoading] = useState(false);
  const [players, setPlayers] = useState<Player[]>([]);
  const [error, setError] = useState('');

  const handleSearch = async (url: string) => {
    setLoading(true);
    setError('');
    setPlayers([]);

    try {
      const response = await fetch(`http://localhost:8000/api/calculate?url=${encodeURIComponent(url)}`);
      if (!response.ok) throw new Error('Failed to fetch data');

      const data = await response.json();
      setPlayers(data.players);
    } catch (err) {
      setError('Failed to load scorecard. Please check the URL.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-800 via-slate-900 to-black text-gray-100 p-6 selection:bg-indigo-500/30">
      <div className="max-w-7xl mx-auto space-y-12">
        {/* Header */}
        <div className="text-center space-y-4 pt-10">
          <div className="inline-flex items-center justify-center p-3 bg-indigo-500/10 rounded-2xl mb-4 ring-1 ring-inset ring-indigo-500/20">
            <Trophy className="w-8 h-8 text-indigo-400" />
          </div>
          <h1 className="text-5xl md:text-6xl font-black tracking-tight text-white mb-2">
            Fantasy <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-purple-500">Calculator</span>
          </h1>
          <p className="text-lg text-gray-400 max-w-xl mx-auto">
            Instant point calculation with premium role-based fairness logic.
          </p>

          <HeroInput onSearch={handleSearch} isLoading={loading} />

          {error && (
            <div className="text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg p-3 max-w-md mx-auto mt-4 text-sm">
              {error}
            </div>
          )}
        </div>

        {/* Results Grid */}
        {players.length > 0 && (
          <div className="animate-in fade-in slide-in-from-bottom-10 duration-700">
            <div className="flex items-center justify-between mb-8 px-2 border-b border-white/5 pb-4">
              <h2 className="text-2xl font-bold flex items-center gap-2">
                <span className="bg-indigo-500 w-1 h-6 rounded-full"></span>
                Leaderboard
              </h2>
              <span className="text-sm text-gray-500 font-mono">{players.length} Players</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {players.map((player, index) => (
                <PlayerCard key={index} player={player} rank={index + 1} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
