
import React, { useState, useCallback, useEffect } from 'react';
import MapBackground from './components/MapBackground';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import SearchBar from './components/SearchBar';
import Controls from './components/Controls';
import ChurchCard from './components/ChurchCard';
import { ChurchLocation, loadChurches } from './src/data/churches';

const App: React.FC = () => {
  const [zoom, setZoom] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [selectedChurch, setSelectedChurch] = useState<ChurchLocation | null>(null);
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [churches, setChurches] = useState<ChurchLocation[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // 앱 시작 시 성당 데이터 로드 + GPS 위치 가져오기
  useEffect(() => {
    // 성당 데이터 로드
    loadChurches().then((data) => {
      setChurches(data);
      setIsLoading(false);
    });

    // GPS 위치 가져오기
    if (navigator.geolocation) {
      setIsSearching(true);
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const { latitude, longitude } = position.coords;
          setUserLocation({ lat: latitude, lng: longitude });
          setIsSearching(false);
        },
        (error) => {
          console.warn('Initial geolocation failed:', error);
          setIsSearching(false);
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 60000
        }
      );
    }
  }, []);

  const handleZoomIn = () => setZoom(prev => Math.min(prev + 0.15, 2));
  const handleZoomOut = () => setZoom(prev => Math.max(prev - 0.15, 0.5));

  const handleFindMass = useCallback(() => {
    setIsSearching(true);
    setSelectedChurch(null);

    if (!navigator.geolocation) {
      alert('브라우저가 위치 서비스를 지원하지 않습니다.');
      setIsSearching(false);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        setUserLocation({ lat: latitude, lng: longitude });
        setIsSearching(false);
      },
      (error) => {
        console.error('Geolocation error:', error);
        alert('위치를 가져올 수 없습니다. 위치 권한을 확인해주세요.');
        setIsSearching(false);
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 30000
      }
    );
  }, []);

  const handleLocate = useCallback(() => {
    handleFindMass();
  }, [handleFindMass]);

  const handleSelectChurch = useCallback((church: ChurchLocation) => {
    setSelectedChurch(church);
  }, []);

  const handleCloseCard = useCallback(() => {
    setSelectedChurch(null);
  }, []);

  return (
    <div className="flex items-center justify-center min-h-screen p-4 md:p-8 overflow-hidden select-none">
      <div className="relative w-full max-w-[1400px] h-[90vh] bg-altar-parchment rounded-[60px] shadow-altar-frame overflow-hidden flex flex-col border border-wood-dark/50">

        {/* Loading Overlay */}
        {isLoading && (
          <div className="absolute inset-0 z-50 bg-altar-parchment/90 flex items-center justify-center">
            <div className="flex flex-col items-center gap-4">
              <div className="w-12 h-12 rounded-full border-4 border-altar-sage/30 border-t-altar-sage animate-spin"></div>
              <p className="text-altar-sage font-medium">성당 데이터 로딩 중...</p>
            </div>
          </div>
        )}

        {/* Map Viewport */}
        <div className="absolute inset-0 z-0">
          <MapBackground
            zoom={zoom}
            center={userLocation || undefined}
            churches={churches}
            onSelectChurch={handleSelectChurch}
          />
        </div>

        {/* Top Left: Header Branding */}
        <div className="absolute top-8 left-8 z-20">
          <Header />
        </div>

        {/* Top Right: Search */}
        <div className="absolute top-8 right-8 z-20 w-72">
          <SearchBar value={searchQuery} onChange={setSearchQuery} />
        </div>

        {/* Right Sidebar: Icons */}
        <Sidebar />

        {/* Bottom Center: Controls (줌인, 줌아웃, 내위치) */}
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-20">
          <Controls
            onZoomIn={handleZoomIn}
            onZoomOut={handleZoomOut}
            onLocate={handleLocate}
            isLocating={isSearching}
          />
        </div>

        {/* Bottom Right: Link back to Blog */}
        <div className="absolute bottom-10 right-12 z-20">
          <a href="https://narthex.kr" target="_blank" rel="noopener noreferrer" className="text-[10px] font-bold uppercase tracking-widest text-altar-sage/60 hover:text-altar-earth transition-colors flex items-center gap-2">
            블로그로
            <span className="material-symbols-outlined text-sm">arrow_outward</span>
          </a>
        </div>

        {/* Church Info Card (Slide-up) */}
        <ChurchCard church={selectedChurch} onClose={handleCloseCard} />

        {/* Church Count Badge */}
        {!isLoading && churches.length > 0 && (
          <div className="absolute top-8 left-1/2 -translate-x-1/2 z-20 px-4 py-2 bg-white/80 backdrop-blur-md rounded-full shadow-md">
            <span className="text-xs font-bold text-altar-sage">
              <span className="text-altar-gold">{churches.length}</span>개 성당
            </span>
          </div>
        )}

      </div>
    </div>
  );
};

export default App;
