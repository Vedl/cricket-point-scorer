import React, { useState, useEffect } from 'react';
import { Trophy, Calendar } from 'lucide-react';
import api from '../api';

function LeaderboardPage() {
    const [gameweek, setGameweek] = useState<string>('cumulative',); // 'cumulative' or number
    const [leaderboard, setLeaderboard] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        fetchLeaderboard();
    }, [gameweek]);

    const fetchLeaderboard = async () => {
        setLoading(true);
        try {
            // We will need to update backend to handle 'cumulative' or just 0
            const endpoint = gameweek === 'cumulative'
                ? '/leaderboard/cumulative'
                : `/leaderboard/${gameweek}`;

            const res = await api.get(endpoint);
            setLeaderboard(res.data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
            <header className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
                <div>
                    <h1 className="text-4xl font-bold flex items-center gap-3">
                        <Trophy className="text-yellow-500" size={40} /> Standings
                    </h1>
                    <p className="text-slate-400 mt-2">Live updates from the T20 World Cup Auction League</p>
                </div>

                <div className="flex items-center gap-2 bg-slate-800 p-1 rounded-lg border border-white/10">
                    <button
                        onClick={() => setGameweek('cumulative')}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${gameweek === 'cumulative' ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-400 hover:text-white'}`}
                    >
                        Overall
                    </button>
                    {[1, 2, 3, 4, 5].map(gw => (
                        <button
                            key={gw}
                            onClick={() => setGameweek(String(gw))}
                            className={`px-3 py-2 rounded-md text-sm font-medium transition-all ${gameweek === String(gw) ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-400 hover:text-white'}`}
                        >
                            GW{gw}
                        </button>
                    ))}
                </div>
            </header>

            {loading ? (
                <div className="text-center py-20 text-slate-500 animate-pulse">Loading standings...</div>
            ) : (
                <div className="space-y-4">
                    {leaderboard.map((entry, index) => (
                        <div key={entry.participant_id} className="bg-slate-800/50 backdrop-blur border border-white/5 rounded-xl p-6 flex flex-col md:flex-row items-center gap-6 hover:bg-slate-800/80 transition-all">

                            {/* Rank */}
                            <div className="flex-shrink-0 w-12 h-12 flex items-center justify-center rounded-full bg-slate-900 border border-slate-700 font-bold text-xl text-slate-300">
                                {index + 1}
                            </div>

                            {/* User Info */}
                            <div className="flex-1 text-center md:text-left">
                                <h3 className="text-xl font-bold text-white">{entry.participant_name}</h3>
                                <div className="text-xs text-slate-400 mt-1">
                                    {entry.best_11?.length || 0} Players Scored
                                </div>
                            </div>

                            {/* Points */}
                            <div className="text-right">
                                <div className="text-sm text-slate-400 uppercase tracking-wider font-semibold">Total Points</div>
                                <div className="text-4xl font-bold text-yellow-500">{entry.gw_points}</div>
                            </div>
                        </div>
                    ))}

                    {leaderboard.length === 0 && (
                        <div className="text-center py-20 text-slate-600">No data found for this period.</div>
                    )}
                </div>
            )}
        </div>
    );
}

export default LeaderboardPage;
