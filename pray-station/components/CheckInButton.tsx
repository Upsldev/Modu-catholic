
import React from 'react';

interface CheckInButtonProps {
  isLoading: boolean;
  onClick: () => void;
}

const CheckInButton: React.FC<CheckInButtonProps> = ({ isLoading, onClick }) => {
  return (
    <button
      disabled={isLoading}
      onClick={onClick}
      className={`flex items-center gap-3 px-8 h-14 rounded-full shadow-xl transition-all group border-b-2 border-black/10 
        ${isLoading ? 'bg-altar-olive cursor-wait' : 'bg-altar-sage hover:bg-[#5b614d] hover:px-10 active:scale-95 text-white'}`}
    >
      <span className={`material-symbols-outlined ${isLoading ? 'animate-spin' : 'text-altar-gold'}`}>
        {isLoading ? 'hourglass_top' : 'location_searching'}
      </span>
      <span className="text-sm font-bold tracking-wider">
        {isLoading ? '찾는 중...' : '성당 찾기'}
      </span>
    </button>
  );
};

export default CheckInButton;
