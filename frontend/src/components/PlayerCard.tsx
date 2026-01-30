import React from 'react';
import { Award, TrendingUp, User } from 'lucide-react';

export interface PlayerStats {
    runs?: number;
    balls_faced?: number;
    fours?: number;
    sixes?: number;
    wickets?: number;
    maidens?: number;
    catches?: number;
    role?: string;
}

export interface Player {
    name: string;
    role: string;
    total_score: number;
    stats: PlayerStats;
}

export const PlayerCard: React.FC<{ player: Player; rank: number }> = ({ player, rank }) => {
    const isTop3 = rank <= 3;
    const rankColor = rank === 1 ? 'text-yellow-400' : rank === 2 ? 'text-gray-300' : rank === 3 ? 'text-amber-600' : 'text-gray-500';

    return (
        <div className={`group relative bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-5 hover:bg-white/10 transition-all duration-300 hover:scale-[1.02] hover:shadow-2xl hover:shadow-indigo-500/10 ${rank === 1 ? 'ring-2 ring-yellow-400/20' : ''}`}>
            <div className="flex justify-between items-start mb-3">
                <div className="flex items-center gap-3">
                    <div className={`text-2xl font-bold ${rankColor}`}>#{rank}</div>
                    <div>
                        <h3 className="font-semibold text-white text-lg leading-tight">{player.name}</h3>
                        <p className="text-xs text-gray-400 uppercase tracking-wider flex items-center gap-1 mt-1">
                            <User size={10} /> {player.role}
                        </p>
                    </div>
                </div>
                <div className="flex flex-col items-end">
                    <div className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-purple-400">
                        {player.total_score.toFixed(1)}
                    </div>
                    <span className="text-[10px] text-gray-500 font-mono uppercase">Points</span>
                </div>
            </div>

            <div className="grid grid-cols-2 gap-2 mt-4 text-xs text-gray-300">
                {player.stats.runs !== undefined && player.stats.runs > 0 && (
                    <div className="bg-white/5 rounded px-2 py-1 flex justify-between">
                        <span>Runs</span> <span className="font-mono text-white">{player.stats.runs} <span className="text-gray-500">({player.stats.balls_faced})</span></span>
                    </div>
                )}
                {player.stats.wickets !== undefined && player.stats.wickets > 0 && (
                    <div className="bg-white/5 rounded px-2 py-1 flex justify-between">
                        <span>Wickets</span> <span className="font-mono text-white">{player.stats.wickets}</span>
                    </div>
                )}
                {player.stats.catches !== undefined && player.stats.catches > 0 && (
                    <div className="bg-white/5 rounded px-2 py-1 flex justify-between">
                        <span>Catches</span> <span className="font-mono text-white">{player.stats.catches}</span>
                    </div>
                )}
                {(player.stats.sixes || 0) > 0 && (
                    <div className="bg-white/5 rounded px-2 py-1 flex justify-between">
                        <span>6s</span> <span className="font-mono text-white">{player.stats.sixes}</span>
                    </div>
                )}
            </div>

            {isTop3 && (
                <div className="absolute -top-2 -right-2 bg-gradient-to-br from-yellow-400 to-orange-500 rounded-full p-1.5 shadow-lg animate-bounce">
                    <Award className="text-white w-4 h-4" />
                </div>
            )}
        </div>
    );
};

export default PlayerCard;
