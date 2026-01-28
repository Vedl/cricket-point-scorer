import React, { useState } from 'react';
import { Gavel, Trophy, Share2, Activity, ArrowRight } from 'lucide-react';
import api from '../api';
import HeroInput from '../components/HeroInput';
import PlayerCard from '../components/PlayerCard';
import Leaderboard from '../components/Leaderboard';

function Home() {
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<any>(null);
    const [error, setError] = useState('');

    const handleCalculate = async (url: string) => {
        setLoading(true);
        setError('');
        setResult(null);

        try {
            const response = await api.get(`/calculate?url=${encodeURIComponent(url)}`);
            setResult(response.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'An error occurred while calculating points');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-12">
            <header className="text-center space-y-4 pt-10">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-yellow-500/10 text-yellow-500 text-sm font-medium border border-yellow-500/20 mb-4">
                    <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-yellow-500"></span>
                    </span>
                    Live Scoring System v2.0
                </div>
                <h1 className="text-5xl md:text-7xl font-bold tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 text-transparent bg-clip-text">
                    Fantasy Cricket <br /> Points Calculator
                </h1>
                <p className="text-slate-400 text-lg max-w-2xl mx-auto leading-relaxed">
                    Calculate hypothetical fantasy points for any match instantly.
                    Perfect for analyzing player performance.
                </p>
            </header>

            <section className="max-w-3xl mx-auto px-4">
                <HeroInput onSubmit={handleCalculate} isLoading={loading} />

                {error && (
                    <div className="mt-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-500 text-center animate-in fade-in slide-in-from-top-4">
                        An error occurred: {error}
                    </div>
                )}
            </section>

            {result && (
                <section className="max-w-5xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-700 px-4 pb-20">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {/* Stats Summary */}
                        <div className="md:col-span-3 bg-slate-800/50 backdrop-blur-sm border border-white/5 rounded-2xl p-6 flex flex-wrap gap-8 justify-center">
                            <div className="text-center">
                                <div className="text-slate-400 text-sm mb-1">Total Players</div>
                                <div className="text-3xl font-bold">{result.players.length}</div>
                            </div>
                            <div className="text-center">
                                <div className="text-slate-400 text-sm mb-1">Highest Score</div>
                                <div className="text-3xl font-bold text-yellow-500">{result.players[0]?.total_score || 0}</div>
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                        <div className="space-y-6">
                            <h2 className="text-2xl font-bold flex items-center gap-2">
                                <Trophy className="text-yellow-500" />
                                Top Performers
                            </h2>
                            <div className="space-y-4">
                                {result.players.slice(0, 5).map((player: any, idx: number) => (
                                    <PlayerCard
                                        key={idx}
                                        player={player}
                                        rank={idx + 1}
                                        isWinner={idx === 0}
                                    />
                                ))}
                            </div>
                        </div>

                        <div className="space-y-6">
                            <h2 className="text-2xl font-bold flex items-center gap-2">
                                <Activity className="text-blue-500" />
                                Full Leaderboard
                            </h2>
                            <Leaderboard players={result.players} />
                        </div>
                    </div>
                </section>
            )}
        </div>
    );
}

export default Home;
