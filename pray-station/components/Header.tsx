
import React from 'react';

const Header: React.FC = () => {
  return (
    <div className="flex flex-col items-start pointer-events-none">
      <div className="flex items-center gap-3 bg-white/30 backdrop-blur-md px-6 py-3 rounded-full border border-white/50 shadow-sm">
        <span className="material-symbols-outlined text-altar-gold text-2xl">temple_buddhist</span>
        <h1 className="text-altar-earth text-lg font-bold tracking-[0.2em] uppercase">Pray-Station</h1>
      </div>
    </div>
  );
};

export default Header;
