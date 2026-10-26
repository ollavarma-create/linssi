import { useState, useEffect, useCallback } from 'react';
import type { ImageRow, ImageDetail, MetaStats, SearchFilters } from './api/client';
import { getImages, getImageDetail, getMeta, getStats } from './api/client';
import FilterPanel from './components/FilterPanel';
import ThumbnailGrid from './components/ThumbnailGrid';
import DetailPanel from './components/DetailPanel';

const PAGE_SIZE = 100;

export default function App() {
  const [stats, setStats] = useState<MetaStats | null>(null);
  const [cameras, setCameras] = useState<string[]>([]);
  const [objects, setObjects] = useState<string[]>([]);
  const [persons, setPersons] = useState<string[]>([]);

  const [images, setImages] = useState<ImageRow[]>([]);
  const [totalImages, setTotalImages] = useState(0);
  const [gridLoading, setGridLoading] = useState(false);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ImageDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [currentFilters, setCurrentFilters] = useState<SearchFilters>({
    query: '', query_and: [], query_or: [],
    date_from: '', date_to: '', camera: '', obj: '', person: '', limit: 50,
  });

  // Load meta on mount
  useEffect(() => {
    getStats().then(setStats).catch(console.error);
    getMeta().then(({ cameras, objects, persons }) => {
      setCameras(cameras);
      setObjects(objects);
      setPersons(persons);
    }).catch(console.error);
  }, []);

  // Run initial search on mount
  useEffect(() => {
    runSearch(currentFilters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runSearch = useCallback(async (filters: SearchFilters) => {
    setCurrentFilters(filters);
    setSelectedId(null);
    setDetail(null);
    setGridLoading(true);
    try {
      const rows = await getImages(filters);
      setImages(rows);
      setTotalImages(rows.length);
    } catch (e) {
      console.error(e);
    } finally {
      setGridLoading(false);
    }
  }, []);

  const handleSelect = useCallback(async (id: number) => {
    setSelectedId(id);
    setDetailLoading(true);
    try {
      const d = await getImageDetail(id);
      setDetail(d);
    } catch (e) {
      console.error(e);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  // "Show more" — increase limit and re-fetch
  const handleLoadMore = useCallback(() => {
    const newLimit = (currentFilters.limit || PAGE_SIZE) + PAGE_SIZE;
    const updated = { ...currentFilters, limit: newLimit };
    runSearch(updated);
  }, [currentFilters, runSearch]);

  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      overflow: 'hidden',
      backgroundColor: 'var(--bg-base)',
      color: 'var(--text)',
    }}>
      {/* Filter panel */}
      <div style={{
        width: 260,
        flexShrink: 0,
        borderRight: '1px solid var(--bg-surface0)',
        backgroundColor: 'var(--bg-mantle)',
        overflowY: 'auto',
      }}>
        <FilterPanel
          stats={stats}
          cameras={cameras}
          objects={objects}
          persons={persons}
          onSearch={runSearch}
        />
      </div>

      {/* Thumbnail grid */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <ThumbnailGrid
          images={images}
          total={totalImages}
          selectedId={selectedId}
          onSelect={handleSelect}
          onLoadMore={handleLoadMore}
          loading={gridLoading}
        />
      </div>

      {/* Detail panel */}
      <div style={{
        width: 380,
        flexShrink: 0,
        borderLeft: '1px solid var(--bg-surface0)',
        backgroundColor: 'var(--bg-mantle)',
        overflowY: 'auto',
      }}>
        <DetailPanel
          imageId={selectedId}
          detail={detail}
          loading={detailLoading}
        />
      </div>
    </div>
  );
}
