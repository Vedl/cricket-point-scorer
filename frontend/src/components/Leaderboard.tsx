import React from 'react';

interface Player {
    name: string;
    role: string;
    total_score: number;
}

interface Props {
    players: Player[];
}

const Leaderboard: React.FC<Props> = ({ players }) => {
    return (
        <div className="bg-slate-900/50 rounded-xl border border-white/5 overflow-hidden">
            <table className="w-full text-sm">
                <thead>
                    <tr className="border-b border-white/10 text-left text-slate-400">
                        <th className="px-4 py-3 font-medium">#</th>
                        <th className="px-4 py-3 font-medium">Player</th>
                        <th className="px-4 py-3 font-medium">Role</th>
                        <th className="px-4 py-3 font-medium text-right">Points</th>
                    </tr>
                </thead>
                <tbody>
                    {players.map((player, index) => (
                        <tr
                            key={index}
                            className="border-b border-white/5 hover:bg-white/5 transition-colors"
                        >
                            <td className="px-4 py-3 text-slate-500 font-mono">{index + 1}</td>
                            <td className="px-4 py-3 font-medium text-white">{player.name}</td>
                            <td className="px-4 py-3 text-slate-400 text-xs uppercase">{player.role}</td>
                            <td className="px-4 py-3 text-right font-bold text-indigo-400">{player.total_score}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

export default Leaderboard;
