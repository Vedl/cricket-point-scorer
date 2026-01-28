import React, { useState, useEffect } from 'react';
import { UserPlus, Plus, Users, ShieldAlert } from 'lucide-react';
import api from '../api';

function AuctionRoom() {
    const [participants, setParticipants] = useState<any[]>([]);
    const [newParticipant, setNewParticipant] = useState('');
    const [selectedParticipant, setSelectedParticipant] = useState<number | null>(null);
    const [playerInput, setPlayerInput] = useState({ name: '', role: 'Bat' });
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        fetchParticipants();
    }, []);

    const fetchParticipants = async () => {
        try {
            const res = await api.get('/participants');
            setParticipants(res.data);
        } catch (err) {
            console.error(err);
        }
    };

    const addParticipant = async () => {
        if (!newParticipant) return;
        try {
            await api.post('/participants', { name: newParticipant });
            setNewParticipant('');
            fetchParticipants();
        } catch (err) {
            alert('Error adding participant');
        }
    };

    const addPlayerToSquad = async () => {
        if (!selectedParticipant || !playerInput.name) return;
        setLoading(true);
        try {
            await api.post('/val/add_to_squad', null, {
                params: {
                    participant_id: selectedParticipant,
                    player_name: playerInput.name,
                    role: playerInput.role
                }
            });
            setPlayerInput({ ...playerInput, name: '' });
            fetchParticipants(); // Refresh to see updated squad count if we had it
            alert('Player Added!');
        } catch (err) {
            alert('Error adding player');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
            <h1 className="text-3xl font-bold">Auction Room</h1>

            {/* Add Participant */}
            <div className="bg-slate-800/50 p-6 rounded-xl border border-white/10 flex gap-4 items-end">
                <div className="flex-1">
                    <label className="text-sm text-slate-400 mb-1 block">New Participant Name</label>
                    <input
                        value={newParticipant}
                        onChange={(e) => setNewParticipant(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2"
                        placeholder="Enter name..."
                    />
                </div>
                <button onClick={addParticipant} className="bg-indigo-600 hover:bg-indigo-500 px-6 py-2 rounded-lg font-medium flex items-center gap-2">
                    <UserPlus size={18} /> Add User
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

                {/* Squad Manager */}
                <div className="bg-slate-800/50 p-6 rounded-xl border border-white/10 space-y-6">
                    <h2 className="text-xl font-bold flex items-center gap-2"><Users className="text-blue-400" /> Manage Squad</h2>

                    <div>
                        <label className="text-sm text-slate-400 mb-1 block">Select Owner</label>
                        <select
                            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-3"
                            onChange={(e) => setSelectedParticipant(Number(e.target.value))}
                            value={selectedParticipant || ''}
                        >
                            <option value="">Select an Owner...</option>
                            {participants.map(p => (
                                <option key={p.id} value={p.id}>{p.name}</option>
                            ))}
                        </select>
                    </div>

                    {selectedParticipant && (
                        <div className="space-y-4 border-t border-white/10 pt-4 animate-in fade-in">
                            <div className="grid grid-cols-3 gap-2">
                                <div className="col-span-2">
                                    <label className="text-xs text-slate-500 mb-1 block">Player Name</label>
                                    <input
                                        value={playerInput.name}
                                        onChange={(e) => setPlayerInput({ ...playerInput, name: e.target.value })}
                                        className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm"
                                        placeholder="Full Name"
                                    />
                                </div>
                                <div>
                                    <label className="text-xs text-slate-500 mb-1 block">Role</label>
                                    <select
                                        value={playerInput.role}
                                        onChange={(e) => setPlayerInput({ ...playerInput, role: e.target.value })}
                                        className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-2 text-sm"
                                    >
                                        <option value="Bat">Bat</option>
                                        <option value="Bowler">Bowl</option>
                                        <option value="Allrounder">AR</option>
                                        <option value="WK">WK</option>
                                    </select>
                                </div>
                            </div>
                            <button
                                onClick={addPlayerToSquad}
                                disabled={loading}
                                className="w-full bg-emerald-600 hover:bg-emerald-500 py-2 rounded-lg font-medium flex justify-center items-center gap-2"
                            >
                                {loading ? 'Adding...' : <><Plus size={18} /> Add to Squad</>}
                            </button>
                        </div>
                    )}
                </div>

                {/* Quick Stats or instructions */}
                <div className="bg-slate-800/30 p-6 rounded-xl border border-white/5 space-y-4 text-slate-400 text-sm">
                    <h3 className="text-white font-semibold flex items-center gap-2"><ShieldAlert size={16} /> Rules</h3>
                    <ul className="list-disc pl-5 space-y-2">
                        <li>Max Squad Size: 19 Players.</li>
                        <li>If 19 players, 1 must be marked as IR (Inactive).</li>
                        <li>Best 11 Composition:
                            <ul className="list-circle pl-5 mt-1 text-slate-500">
                                <li>WK: 1-4</li>
                                <li>Bat: 3-6</li>
                                <li>AR: 1-4</li>
                                <li>Bowl: 3-6</li>
                            </ul>
                        </li>
                    </ul>
                </div>

            </div>
        </div>
    );
}

export default AuctionRoom;
