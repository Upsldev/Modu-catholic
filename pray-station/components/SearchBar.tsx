
import React, { useState } from 'react';

interface SearchBarProps {
  value: string;
  onChange: (val: string) => void;
}

const SearchBar: React.FC<SearchBarProps> = ({ value, onChange }) => {
  // 검색 실행 - narthex.kr로 리다이렉트
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (value.trim()) {
      // narthex.kr 검색 페이지로 이동
      window.open(`https://narthex.kr/?s=${encodeURIComponent(value.trim())}`, '_blank');
    }
  };

  return (
    <form onSubmit={handleSearch}>
      <label className="flex items-center gap-3 w-full h-12 px-5 rounded-full bg-white/40 backdrop-blur-md border border-white/60 shadow-sm transition-all focus-within:bg-white/60">
        <span className="material-symbols-outlined text-altar-sage/70">search</span>
        <input
          className="w-full bg-transparent border-none focus:ring-0 text-altar-earth placeholder-altar-olive font-medium text-sm h-full p-0"
          placeholder="성당 이름 검색..."
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        <button
          type="submit"
          className="flex-shrink-0 w-8 h-8 rounded-full bg-altar-sage/20 hover:bg-altar-sage/40 flex items-center justify-center transition-colors"
        >
          <span className="material-symbols-outlined text-altar-sage text-lg">arrow_forward</span>
        </button>
      </label>
    </form>
  );
};

export default SearchBar;
