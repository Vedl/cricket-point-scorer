import React, { useState } from 'react';
import { Settings, Play, Database } from 'lucide-react';
import api from '../api';

function AdminDashboard() {
    const [gameweek, setGameweek] = useState(1);
    const [urls, setUrls] = useState('');
    const [loading, setLoading] = useState(false);
    const [logs, setLogs] = useState<string[]>([]);

    const handleProcess = async () => {
        setLoading(true);
        setLogs(['Starting processing process...']);
        try {
            const urlList = urls.split('\n').filter(u => u.trim());
            if (urlList.length === 0) {
                alert("No URLs provided");
                setLoading(false);
                return;
            }

            setLogs(prev => [...prev, `Processing ${urlList.length} matches for Gameweek ${gameweek}...`]);

            const res = await api.post('/gameweek/process', {
                gameweek: Number(gameweek),
                match_urls: urlList
            });

            setLogs(prev => [...prev, '✓ Processing Complete!', 'Leaderboard Updated.']);
            console.log(res.data);
        } catch (err) {
            setLogs(prev => [...prev, '❌ Error occurred during processing.']);
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="max-w-4xl mx-auto px-4 py-8 space-y-8">
            <h1 className="text-3xl font-bold flex items-center gap-3">
                <Settings className="text-slate-400" /> League Admin
            </h1>

            <div className="bg-slate-800/50 border border-white/10 p-6 rounded-xl space-y-6">
                <h2 className="text-xl font-bold">Gameweek Manager</h2>

                <div>
                    <label className="block text-sm text-slate-400 mb-1">Gameweek Number</label>
                    <input
                        type="number"
                        className="bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 w-24"
                        value={gameweek}
                        onChange={(e) => setGameweek(Number(e.target.value))}
                    />
                </div>

                <div>
                    <label className="block text-sm text-slate-400 mb-1">Match URLs (One per line)</label>
                    <textarea
                        className="w-full h-48 bg-slate-900 border border-slate-700 rounded-lg p-4 font-mono text-xs"
                        placeholder="https://www.cricbuzz.com/live-cricket-scores/..."
                        value={urls}
                        onChange={(e) => setUrls(e.target.value)}
                    />
                </div>

                <button
                    onClick={handleProcess}
                    disabled={loading}
                    className={`
                px-6 py-3 rounded-lg font-bold flex items-center gap-2
                ${loading ? 'bg-slate-600 cursor-not-allowed' : 'bg-green-600 hover:bg-green-500'}
            `}
                >
                    <Play size={18} fill="currentColor" />
                    {loading ? 'Processing Scrapers...' : 'Run Gameweek Processor'}
                </button>

                {logs.length > 0 && (
                    <div className="bg-black/50 p-4 rounded-lg font-mono text-sm space-y-1 text-green-400 border border-white/5">
                        {logs.map((log, i) => <div key={i}>{log}</div>)}
                    </div>
                )}
            </div>

            <div className="bg-slate-800/30 p-6 rounded-xl border border-white/5 opacity-50 pointer-events-none">
                <h2 className="text-lg font-bold flex items-center gap-2"><Database size={16} /> Database Actions</h2>
                <p className="text-sm text-slate-500">Reset League, Clear Cache (Coming Soon)</p>
            </div>
        </div>
    );
}

export default AdminDashboard;
