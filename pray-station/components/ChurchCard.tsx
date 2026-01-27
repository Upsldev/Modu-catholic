import React from 'react';
import { ChurchLocation } from '../src/data/churches';

interface ChurchCardProps {
    church: ChurchLocation | null;
    onClose: () => void;
}

const ChurchCard: React.FC<ChurchCardProps> = ({ church, onClose }) => {
    if (!church) return null;

    return (
        <div className="absolute bottom-0 left-0 right-0 z-30 px-4 pb-6 pt-2 animate-slide-up">
            {/* Backdrop blur */}
            <div
                className="absolute inset-0 bg-gradient-to-t from-altar-parchment/95 via-altar-parchment/80 to-transparent pointer-events-none"
            />

            {/* Card Container */}
            <div className="relative max-w-lg mx-auto bg-white/90 backdrop-blur-xl rounded-3xl shadow-2xl border border-altar-gold/20 overflow-hidden">
                {/* Close Button */}
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 z-10 w-8 h-8 rounded-full bg-altar-parchment/80 flex items-center justify-center hover:bg-altar-olive/20 transition-colors"
                >
                    <span className="material-symbols-outlined text-altar-earth text-lg">close</span>
                </button>

                {/* Church Type Badge */}
                <div className="absolute top-4 left-4 z-10">
                    <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest text-white
            ${church.type === 'basilica' ? 'bg-altar-gold' :
                            church.type === 'chapel' ? 'bg-altar-olive' : 'bg-altar-sage'}`}>
                        {church.type === 'basilica' ? '대성당' :
                            church.type === 'chapel' ? '성지' : '본당'}
                    </span>
                </div>

                {/* Content */}
                <div className="p-6 pt-14">
                    {/* Church Name */}
                    <h2 className="text-2xl font-bold text-altar-earth mb-1">{church.name}</h2>

                    {/* Address */}
                    <p className="text-sm text-altar-sage mb-4 flex items-center gap-1">
                        <span className="material-symbols-outlined text-sm">location_on</span>
                        {church.address}
                    </p>

                    {/* Divider */}
                    <div className="h-px bg-gradient-to-r from-transparent via-altar-gold/30 to-transparent my-4" />

                    {/* Action Buttons - 전화 + 미사시간 보기 */}
                    <div className="flex gap-3">
                        {/* 전화 버튼 */}
                        {church.phone && (
                            <a
                                href={`tel:${church.phone}`}
                                className="flex-1 h-14 rounded-2xl bg-altar-parchment flex items-center justify-center gap-3 hover:bg-altar-olive/20 transition-colors border border-altar-gold/20"
                            >
                                <span className="material-symbols-outlined text-altar-sage text-xl">call</span>
                                <div className="text-left">
                                    <p className="text-[10px] text-altar-sage uppercase tracking-wider">전화</p>
                                    <p className="text-sm font-bold text-altar-earth">{church.phone}</p>
                                </div>
                            </a>
                        )}

                        {/* 미사시간 보기 버튼 (블로그 연결) */}
                        <a
                            href={church.blogUrl || `https://narthex.kr/?s=${encodeURIComponent(church.name)}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex-1 h-14 rounded-2xl bg-altar-sage text-white font-bold text-sm flex items-center justify-center gap-2 hover:bg-altar-earth transition-colors shadow-lg"
                        >
                            <span className="material-symbols-outlined text-lg">schedule</span>
                            미사시간 보기
                        </a>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ChurchCard;
