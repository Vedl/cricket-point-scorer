import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Gavel, Trophy, Calculator, Settings } from 'lucide-react';

const Navbar = () => {
    const location = useLocation();

    const isActive = (path: string) => location.pathname === path;

    const navItems = [
        { path: '/', label: 'Calculator', icon: Calculator },
        { path: '/auction', label: 'Auction Room', icon: Gavel },
        { path: '/admin', label: 'League Admin', icon: Settings },
        { path: '/leaderboard', label: 'Standings', icon: Trophy },
    ];

    return (
        <nav className="fixed bottom-0 left-0 w-full bg-slate-900/90 backdrop-blur-md border-t border-white/10 p-4 md:static md:top-0 md:border-t-0 md:border-b z-50">
            <div className="max-w-6xl mx-auto flex justify-around md:justify-end gap-2 md:gap-6">
                {navItems.map((item) => {
                    const Icon = item.icon;
                    const active = isActive(item.path);
                    return (
                        <Link
                            key={item.path}
                            to={item.path}
                            className={`flex flex-col md:flex-row items-center gap-1 md:gap-2 px-4 py-2 rounded-lg transition-all
                 ${active ? 'bg-indigo-600/20 text-indigo-400' : 'text-slate-400 hover:text-white hover:bg-white/5'}
               `}
                        >
                            <Icon size={20} />
                            <span className="text-xs md:text-sm font-medium">{item.label}</span>
                        </Link>
                    )
                })}
            </div>
        </nav>
    );
};

export default Navbar;
