import React, { useState } from 'react';
import { Search } from 'lucide-react';

interface Props {
    onSearch: (url: string) => void;
    isLoading: boolean;
}

export const HeroInput: React.FC<Props> = ({ onSearch, isLoading }) => {
    const [url, setUrl] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (url.trim()) onSearch(url);
    };

    return (
        <div className="relative w-full max-w-2xl mx-auto mt-10">
            <div className="absolute inset-0 bg-gradient-to-r from-indigo-500 to-purple-500 blur-xl opacity-30 animate-pulse"></div>
            <form onSubmit={handleSubmit} className="relative group">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <Search className="h-5 w-5 text-gray-400 group-focus-within:text-indigo-400 transition-colors" />
                </div>
                <input
                    type="text"
                    className="block w-full pl-12 pr-4 py-4 bg-white/10 backdrop-blur-md border border-white/10 rounded-2xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:bg-white/15 transition-all shadow-xl"
                    placeholder="Paste Cricbuzz Scorecard URL..."
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    disabled={isLoading}
                />
                <button
                    type="submit"
                    disabled={isLoading}
                    className="absolute right-2 top-2 bottom-2 px-6 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-xl transition-all shadow-lg shadow-indigo-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {isLoading ? 'Analysing...' : 'Calculate'}
                </button>
            </form>
        </div>
    );
};

export default HeroInput;
