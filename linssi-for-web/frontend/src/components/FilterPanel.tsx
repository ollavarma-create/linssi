import { useState, useRef } from 'react';
import type { SearchFilters, MetaStats } from '../api/client';
import { parseQuery } from '../api/client';

interface Props {
  stats: MetaStats | null;
  cameras: string[];
  objects: string[];
  persons: string[];
  onSearch: (filters: SearchFilters) => void;
}

function AutocompleteInput({
  value,
  onChange,
  placeholder,
  title,
  suggestions,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  title?: string;
  suggestions: string[];
}) {
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtered = value
    ? suggestions.filter((s) => s.toLowerCase().includes(value.toLowerCase()))
    : suggestions;

  return (
    <div style={{ position: 'relative' }}>
      <input
        ref={inputRef}
        value={value}
        placeholder={placeholder}
        title={title}
        onChange={(e) => { onChange(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      {open && filtered.length > 0 && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          right: 0,
          zIndex: 100,
          backgroundColor: 'var(--bg-surface0)',
          border: '1px solid var(--bg-surface1)',
          borderRadius: 4,
          maxHeight: 160,
          overflowY: 'auto',
        }}>
          {filtered.slice(0, 30).map((s) => (
            <div
              key={s}
              onMouseDown={() => { onChange(s); setOpen(false); }}
              style={{
                padding: '4px 8px',
                fontSize: 12,
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface1)')}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '')}
            >
              {s}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function FilterPanel({ stats, cameras, objects, persons, onSearch }: Props) {
  const [query, setQuery] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [camera, setCamera] = useState('');
  const [obj, setObj] = useState('');
  const [person, setPerson] = useState('');
  const [limit, setLimit] = useState(50);

  function buildFilters(): SearchFilters {
    const parsed = parseQuery(query);
    return {
      query: query.trim(),
      query_and: parsed.query_and,
      query_or: parsed.query_or,
      date_from: dateFrom.trim(),
      date_to: dateTo.trim(),
      camera: camera.trim(),
      obj: obj.trim(),
      person: person.trim(),
      limit,
    };
  }

  function handleSearch() {
    onSearch(buildFilters());
  }

  function handleClear() {
    setQuery(''); setDateFrom(''); setDateTo('');
    setCamera(''); setObj(''); setPerson(''); setLimit(50);
    onSearch({ query: '', query_and: [], query_or: [], date_from: '', date_to: '', camera: '', obj: '', person: '', limit: 50 });
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') handleSearch();
  }

  const fieldStyle: React.CSSProperties = { marginBottom: 8 };
  const labelStyle: React.CSSProperties = { fontSize: 11, color: 'var(--subtext)', marginBottom: 2, display: 'block' };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '8px 10px', overflowY: 'auto' }}>
      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 10, color: 'var(--accent)' }}>Linssi For Web <span style={{ fontWeight: 400, fontSize: 11, opacity: 0.6 }}>v0.2.0</span></div>

      <div style={fieldStyle}>
        <label style={labelStyle}>Search</label>
        <input
          value={query}
          placeholder="file, description, camera, object, person…"
          title={
            'Search from all text fields at the same time.\n\nSyntax:\n  Jari & dog   → AND: both must exist\n  Jari, Vesa   → OR: either is enough\n  dog          → one search word\n\nYOLO search is partial — "dog" also finds "hot dog".\nUse Object field for exact search.'
          }
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
        />
      </div>

      <div style={fieldStyle}>
        <label style={labelStyle}>Date from</label>
        <input value={dateFrom} placeholder="YYYY-MM-DD" title="Lower date bound (YYYY-MM-DD)" onChange={(e) => setDateFrom(e.target.value)} onKeyDown={handleKeyDown} />
      </div>

      <div style={fieldStyle}>
        <label style={labelStyle}>Date to</label>
        <input value={dateTo} placeholder="YYYY-MM-DD" title="Upper date bound (YYYY-MM-DD)" onChange={(e) => setDateTo(e.target.value)} onKeyDown={handleKeyDown} />
      </div>

      <div style={fieldStyle}>
        <label style={labelStyle}>Camera</label>
        <AutocompleteInput value={camera} onChange={setCamera} placeholder="e.g. Canon" title="Partial match against camera make or model" suggestions={cameras} />
      </div>

      <div style={fieldStyle}>
        <label style={labelStyle}>Object</label>
        <AutocompleteInput value={obj} onChange={setObj} placeholder="e.g. dog" title="Partial match against YOLO class names" suggestions={objects} />
      </div>

      <div style={fieldStyle}>
        <label style={labelStyle}>Person</label>
        <AutocompleteInput value={person} onChange={setPerson} placeholder="e.g. Hemmo" title="Exact match against identified person name" suggestions={persons} />
      </div>

      <div style={{ ...fieldStyle, display: 'flex', alignItems: 'center', gap: 8 }}>
        <label style={{ ...labelStyle, marginBottom: 0, whiteSpace: 'nowrap' }}>Limit</label>
        <input
          type="number"
          value={limit}
          min={0}
          title="Max results (0 = all)"
          onChange={(e) => setLimit(Number(e.target.value))}
          onKeyDown={handleKeyDown}
          style={{ width: 70 }}
        />
      </div>

      <div style={{ display: 'flex', gap: 6, marginTop: 4, marginBottom: 12 }}>
        <button className="primary" onClick={handleSearch} style={{ flex: 1 }}>Search</button>
        <button onClick={handleClear} style={{ flex: 1 }}>Clear</button>
      </div>

      {stats && (
        <div style={{ fontSize: 11, color: 'var(--subtext)', lineHeight: 1.6 }}>
          <div style={{ fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>
            📊 {stats.total_images} images
          </div>
          {(stats.date_from || stats.date_to) && (
            <div>📅 {(stats.date_from || '?').slice(0, 10)} – {(stats.date_to || '?').slice(0, 10)}</div>
          )}

          {stats.top_cameras.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontWeight: 600, color: 'var(--text)' }}>📷 Top cameras</div>
              {stats.top_cameras.map(([name, count]) => (
                <div key={name}>  • {name}: {count}</div>
              ))}
            </div>
          )}

          {stats.top_objects.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontWeight: 600, color: 'var(--text)' }}>🎯 Top objects</div>
              {stats.top_objects.map(([name, count]) => (
                <div key={name}>  • {name}: {count}</div>
              ))}
            </div>
          )}

          {stats.top_persons.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontWeight: 600, color: 'var(--text)' }}>👤 Top people</div>
              {stats.top_persons.map(([name, count]) => (
                <div key={name}>  • {name}: {count}</div>
              ))}
            </div>
          )}

          {stats.top_locations.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontWeight: 600, color: 'var(--text)' }}>📍 Top locations</div>
              {stats.top_locations.map(([coords, count]) => (
                <div key={coords}>  • {coords}: {count}</div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
