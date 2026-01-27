
import React from 'react';

interface ControlsProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onLocate: () => void;
  isLocating?: boolean;
}

const Controls: React.FC<ControlsProps> = ({ onZoomIn, onZoomOut, onLocate, isLocating }) => {
  return (
    <div className="flex items-center gap-2 bg-white/60 backdrop-blur-md rounded-full px-2 py-2 shadow-xl border border-white/80">
      {/* 줌 아웃 */}
      <button
        onClick={onZoomOut}
        className="size-11 rounded-full bg-white/80 flex items-center justify-center text-altar-sage hover:bg-altar-parchment transition-colors"
      >
        <span className="material-symbols-outlined text-xl">remove</span>
      </button>

      {/* 내 위치 - 메인 버튼 */}
      <button
        onClick={onLocate}
        disabled={isLocating}
        className={`flex items-center gap-2 px-6 h-12 rounded-full font-bold text-sm transition-all
          ${isLocating
            ? 'bg-altar-olive text-white cursor-wait'
            : 'bg-altar-sage text-white hover:bg-[#5b614d] active:scale-95'}`}
      >
        <span className={`material-symbols-outlined ${isLocating ? 'animate-spin' : ''}`}>
          {isLocating ? 'hourglass_top' : 'my_location'}
        </span>
        <span>{isLocating ? '찾는 중...' : '내 위치'}</span>
      </button>

      {/* 줌 인 */}
      <button
        onClick={onZoomIn}
        className="size-11 rounded-full bg-white/80 flex items-center justify-center text-altar-sage hover:bg-altar-parchment transition-colors"
      >
        <span className="material-symbols-outlined text-xl">add</span>
      </button>
    </div>
  );
};

export default Controls;
