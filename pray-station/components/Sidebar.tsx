
import React from 'react';

const Sidebar: React.FC = () => {
  // Simplified menu - just the essential church icon
  const beads = [
    { icon: 'church', label: '성당', active: true },
  ];

  return (
    <div className="absolute right-6 top-1/2 -translate-y-1/2 z-30 flex flex-col items-center gap-6 prayer-bead-chain pointer-events-none">
      {beads.map((bead, i) => (
        <Bead key={i} {...bead} />
      ))}
    </div>
  );
};

interface BeadProps {
  icon: string;
  label: string;
  active?: boolean;
}

const Bead: React.FC<BeadProps> = ({ icon, label, active }) => (
  <div className="group relative flex items-center pointer-events-auto">
    <div className={`absolute right-full mr-4 opacity-0 group-hover:opacity-100 transition-opacity ${active ? 'bg-altar-sage text-white' : 'bg-white/90 text-altar-earth border border-altar-gold/20'} text-[10px] font-bold px-3 py-1.5 rounded-full uppercase tracking-widest whitespace-nowrap shadow-xl`}>
      {label}
    </div>
    <button className={`size-${active ? '14' : '12'} rounded-full ${active ? 'bg-altar-sage text-white border-2 border-white/20' : 'bg-altar-parchment text-altar-sage border border-wood-dark/30'} shadow-bead-raised flex items-center justify-center transition-all hover:scale-110 active:shadow-bead-inset active:scale-95`}>
      <span className={`material-symbols-outlined text-${active ? '2xl' : 'xl'}`}>{icon}</span>
    </button>
  </div>
);

export default Sidebar;
