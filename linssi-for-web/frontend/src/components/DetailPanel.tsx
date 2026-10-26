import { useState, useEffect } from 'react';
import type { ImageDetail } from '../api/client';
import { getPreviewUrl } from '../api/client';
import { basename, formatFileSize } from '../utils';

interface Props {
  imageId: number | null;
  detail: ImageDetail | null;
  loading: boolean;
}

function ExifRow({ label, value }: { label: string; value: React.ReactNode }) {
  if (!value && value !== 0) return null;
  return (
    <tr>
      <td style={{ color: 'var(--subtext)', fontSize: 11, padding: '2px 6px 2px 0', whiteSpace: 'nowrap', verticalAlign: 'top' }}>{label}</td>
      <td style={{ fontSize: 11, padding: '2px 0', wordBreak: 'break-all' }}>{value}</td>
    </tr>
  );
}

export default function DetailPanel({ imageId, detail, loading }: Props) {
  const [copied, setCopied] = useState(false);

  useEffect(() => { setCopied(false); }, [imageId]);

  function copyPath() {
    if (!detail?.file_path) return;
    const text = detail.file_path;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      });
    } else {
      // Fallback for non-secure contexts (plain HTTP on LAN)
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      try {
        document.execCommand('copy');
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } finally {
        document.body.removeChild(ta);
      }
    }
  }

  if (!imageId) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--subtext)', fontSize: 14 }}>
        Select an image
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--subtext)', fontSize: 14 }}>
        Loading…
      </div>
    );
  }

  if (!detail) return null;

  const hasGps = detail.gps_lat != null && detail.gps_lon != null;
  const osmUrl = hasGps
    ? `https://www.openstreetmap.org/?mlat=${detail.gps_lat}&mlon=${detail.gps_lon}&zoom=15`
    : null;

  const camera = [detail.camera_make, detail.camera_model].filter(Boolean).join(' ') || null;
  const objectNames = detail.objects.map((o) => o.class_name).join(', ') || null;
  const personNames = detail.persons.map((p) => p.person_name).join(', ') || null;

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <img
        src={getPreviewUrl(imageId)}
        alt={basename(detail.file_path)}
        style={{ width: '100%', borderRadius: 4, objectFit: 'contain', maxHeight: 320, backgroundColor: 'var(--bg-surface0)' }}
      />

      <div style={{ display: 'flex', gap: 6 }}>
        <button onClick={copyPath} title="Copy file path to clipboard" style={{ fontSize: 12 }}>
          {copied ? '✓ Copied' : '📋 Copy path'}
        </button>
        {osmUrl && (
          <a href={osmUrl} target="_blank" rel="noreferrer">
            <button title="Open location in OpenStreetMap" style={{ fontSize: 12 }}>📂 Open in OSM</button>
          </a>
        )}
      </div>

      <table style={{ borderCollapse: 'collapse', width: '100%' }}>
        <tbody>
          <ExifRow label="File" value={basename(detail.file_path)} />
          <ExifRow label="Date" value={detail.date_taken ? detail.date_taken.slice(0, 19).replace('T', ' ') : null} />
          <ExifRow label="Camera" value={camera} />
          <ExifRow
            label="GPS"
            value={
              hasGps && osmUrl ? (
                <a href={osmUrl} target="_blank" rel="noreferrer">
                  {detail.gps_lat!.toFixed(5)}, {detail.gps_lon!.toFixed(5)}
                </a>
              ) : null
            }
          />
          <ExifRow label="Focal length" value={detail.focal_length ? `${detail.focal_length} mm` : null} />
          <ExifRow label="Aperture" value={detail.aperture ? `f/${detail.aperture}` : null} />
          <ExifRow label="ISO" value={detail.iso} />
          <ExifRow label="Exposure" value={detail.exposure_time} />
          <ExifRow label="Dimensions" value={detail.width && detail.height ? `${detail.width} × ${detail.height}` : null} />
          <ExifRow label="File size" value={detail.file_size ? formatFileSize(detail.file_size) : null} />
          <ExifRow label="Objects" value={objectNames} />
          <ExifRow label="Persons" value={personNames} />
        </tbody>
      </table>

      {detail.description && (
        <div>
          <div style={{ fontSize: 11, color: 'var(--subtext)', marginBottom: 4 }}>LLM description</div>
          <textarea
            readOnly
            value={detail.description}
            style={{ width: '100%', height: 100, resize: 'vertical', fontSize: 11 }}
          />
        </div>
      )}
    </div>
  );
}
