import { getThumbnailUrl } from '../api/client';
import type { ImageRow } from '../api/client';
import { basename } from '../utils';

interface Props {
  images: ImageRow[];
  total: number;
  selectedId: number | null;
  onSelect: (id: number) => void;
  onLoadMore: () => void;
  loading: boolean;
}

export default function ThumbnailGrid({ images, total, selectedId, onSelect, onLoadMore, loading }: Props) {
  const allLoaded = images.length >= total && total > 0;

  if (!loading && images.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--subtext)', fontSize: 14 }}>
        No images found
      </div>
    );
  }

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: 8 }}>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))',
        gap: 6,
      }}>
        {images.map((img) => (
          <div
            key={img.id}
            onClick={() => onSelect(img.id)}
            style={{
              cursor: 'pointer',
              borderRadius: 4,
              overflow: 'hidden',
              border: img.id === selectedId ? '2px solid var(--accent)' : '2px solid transparent',
              backgroundColor: 'var(--bg-surface0)',
            }}
          >
            <img
              src={getThumbnailUrl(img.id)}
              loading="lazy"
              alt={basename(img.file_path)}
              style={{ width: '100%', height: 100, objectFit: 'cover', display: 'block' }}
            />
            <div style={{
              padding: '2px 4px',
              fontSize: 10,
              color: 'var(--subtext)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}>
              {basename(img.file_path)}
            </div>
          </div>
        ))}
      </div>

      <div style={{ textAlign: 'center', padding: '12px 0', fontSize: 12, color: 'var(--subtext)' }}>
        {loading && <span>Loading…</span>}
        {!loading && allLoaded && images.length > 0 && (
          <span>All {images.length} images loaded</span>
        )}
        {!loading && !allLoaded && images.length > 0 && (
          <button onClick={onLoadMore} style={{ fontSize: 12 }}>
            Show more ({images.length} / {total} loaded)
          </button>
        )}
      </div>
    </div>
  );
}
