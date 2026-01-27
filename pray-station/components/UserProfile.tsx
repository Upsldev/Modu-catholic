
import React from 'react';

interface UserProfileProps {
  name: string;
  level: string;
}

const UserProfile: React.FC<UserProfileProps> = ({ name, level }) => {
  return (
    <div className="flex items-center gap-3 bg-white/40 backdrop-blur-md p-1.5 pr-4 rounded-full border border-white/60 shadow-sm cursor-pointer hover:bg-white/50 transition-colors">
      <div 
        className="bg-center bg-no-repeat bg-cover rounded-full size-10 border border-white shadow-inner" 
        style={{ backgroundImage: `url('https://picsum.photos/seed/monk/80/80')` }}
      ></div>
      <div className="flex flex-col">
        <span className="text-altar-earth text-[10px] font-extrabold uppercase tracking-wider">{name}</span>
        <span className="text-altar-gold text-[9px] font-bold uppercase">{level}</span>
      </div>
    </div>
  );
};

export default UserProfile;
