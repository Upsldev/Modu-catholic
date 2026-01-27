import React, { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, useMap } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import L from 'leaflet';
import { SEOUL_CENTER, ChurchLocation } from '../src/data/churches';
import 'leaflet/dist/leaflet.css';

interface MapBackgroundProps {
  zoom: number;
  center?: { lat: number; lng: number };
  churches: ChurchLocation[];
  onSelectChurch: (church: ChurchLocation) => void;
}

// 성당 마커 아이콘 (이름 라벨 포함)
const createChurchIcon = (church: ChurchLocation) => {
  const isBasilica = church.type === 'basilica';
  const iconSize = isBasilica ? 44 : 38;

  // 이름이 너무 길면 자르기
  const displayName = church.name.length > 8
    ? church.name.substring(0, 7) + '...'
    : church.name;

  return L.divIcon({
    className: 'custom-marker-wrapper',
    html: `
      <div class="church-marker-container">
        <div class="church-label">${displayName}</div>
        <div class="custom-marker ${isBasilica ? 'basilica' : ''}">
          <span class="material-symbols-outlined marker-icon">church</span>
        </div>
        <div class="marker-shadow"></div>
      </div>
    `,
    iconSize: [120, iconSize + 30],
    iconAnchor: [60, iconSize + 20],
  });
};

// 클러스터 아이콘 (그룹화된 마커)
const createClusterCustomIcon = (cluster: any) => {
  const count = cluster.getChildCount();
  let size = 'small';
  if (count > 50) size = 'large';
  else if (count > 20) size = 'medium';

  return L.divIcon({
    html: `<div class="cluster-marker cluster-${size}">
      <span>${count}</span>
    </div>`,
    className: 'custom-cluster-wrapper',
    iconSize: [50, 50],
    iconAnchor: [25, 25],
  });
};

// 사용자 위치 아이콘
const userLocationIcon = L.divIcon({
  className: 'user-location-wrapper',
  html: `
    <div class="user-marker-container">
      <div class="user-label">📍 내 위치</div>
      <div class="user-pulse"></div>
      <div class="user-dot">
        <span class="material-symbols-outlined text-white" style="font-size: 20px;">my_location</span>
      </div>
    </div>
  `,
  iconSize: [80, 80],
  iconAnchor: [40, 50],
});

// Map controller component
interface MapControllerProps {
  center: { lat: number; lng: number };
  zoom: number;
}

const MapController: React.FC<MapControllerProps> = ({ center, zoom }) => {
  const map = useMap();

  useEffect(() => {
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 100);

    const handleResize = () => map.invalidateSize();
    window.addEventListener('resize', handleResize);

    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', handleResize);
    };
  }, [map]);

  useEffect(() => {
    map.setView([center.lat, center.lng], 14, { animate: true, duration: 1 });
  }, [center, map]);

  useEffect(() => {
    const currentZoom = map.getZoom();
    const targetZoom = Math.round(12 + (zoom - 0.5) * 4);
    if (Math.abs(currentZoom - targetZoom) > 0.5) {
      map.setZoom(targetZoom, { animate: true });
    }
  }, [zoom, map]);

  return null;
};

const MapBackground: React.FC<MapBackgroundProps> = ({ zoom, center, churches, onSelectChurch }) => {
  const mapCenter = center || SEOUL_CENTER;

  // 마커 메모이제이션으로 불필요한 재렌더링 방지
  const churchMarkers = useMemo(() => {
    return churches.map((church) => (
      <Marker
        key={church.id}
        position={[church.lat, church.lng]}
        icon={createChurchIcon(church)}
        eventHandlers={{
          click: () => onSelectChurch(church),
        }}
      />
    ));
  }, [churches, onSelectChurch]);

  return (
    <div className="absolute inset-0 bg-[#e8e4d8] overflow-hidden">
      {/* Map Container with Parchment Filter */}
      <div className="absolute inset-0 map-texture">
        <MapContainer
          center={[mapCenter.lat, mapCenter.lng]}
          zoom={14}
          zoomControl={false}
          attributionControl={false}
          className="w-full h-full"
          style={{ height: '100%', width: '100%', background: '#e8e4d8' }}
        >
          {/* 한국어 지도 타일 - OpenStreetMap */}
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; OpenStreetMap'
          />

          {/* Map Controller for zoom/pan */}
          <MapController center={mapCenter} zoom={zoom} />

          {/* 마커 클러스터링 - 줌 아웃 시 성능 최적화 */}
          <MarkerClusterGroup
            chunkedLoading
            iconCreateFunction={createClusterCustomIcon}
            maxClusterRadius={60}
            spiderfyOnMaxZoom={true}
            showCoverageOnHover={false}
            zoomToBoundsOnClick={true}
            disableClusteringAtZoom={16}
          >
            {churchMarkers}
          </MarkerClusterGroup>

          {/* User Location Marker */}
          {center && (
            <Marker
              position={[center.lat, center.lng]}
              icon={userLocationIcon}
              zIndexOffset={1000}
            />
          )}
        </MapContainer>
      </div>

      {/* Decorative Vignette Overlay */}
      <div className="absolute inset-0 bg-[radial-gradient(circle,transparent_40%,rgba(75,72,63,0.12)_100%)] pointer-events-none" />
    </div>
  );
};

export default MapBackground;
