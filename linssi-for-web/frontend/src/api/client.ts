import axios from 'axios';

export interface ObjectDetection {
  class_name: string;
  confidence: number;
  bbox_x1: number;
  bbox_y1: number;
  bbox_x2: number;
  bbox_y2: number;
}

export interface FaceDetection {
  person_name: string;
  confidence: number;
  bbox_x1: number;
  bbox_y1: number;
  bbox_x2: number;
  bbox_y2: number;
}

export interface ImageRow {
  id: number;
  file_path: string;
  date_taken: string | null;
  camera_model: string | null;
  objects: string | null;
  persons: string | null;
}

export interface ImageDetail {
  file_path: string;
  file_size: number | null;
  camera_make: string | null;
  camera_model: string | null;
  date_taken: string | null;
  gps_lat: number | null;
  gps_lon: number | null;
  focal_length: number | null;
  aperture: number | null;
  iso: number | null;
  exposure_time: string | null;
  width: number | null;
  height: number | null;
  orientation: number | null;
  description: string | null;
  objects: ObjectDetection[];
  persons: FaceDetection[];
}

export interface MetaStats {
  total_images: number;
  completed: Record<string, number>;
  date_from: string;
  date_to: string;
  top_cameras: [string, number][];
  top_objects: [string, number][];
  top_persons: [string, number][];
  top_locations: [string, number][];
}

export interface SearchFilters {
  query: string;
  query_and: string[];
  query_or: string[];
  date_from: string;
  date_to: string;
  camera: string;
  obj: string;
  person: string;
  limit: number;
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '',
  paramsSerializer: (params) => {
    const parts: string[] = [];
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null || value === '') continue;
      if (Array.isArray(value)) {
        for (const v of value) {
          parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(v)}`);
        }
      } else {
        parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
      }
    }
    return parts.join('&');
  },
});

export async function getImages(filters: SearchFilters): Promise<ImageRow[]> {
  const params: Record<string, unknown> = {
    query: filters.query,
    date_from: filters.date_from,
    date_to: filters.date_to,
    camera: filters.camera,
    obj: filters.obj,
    person: filters.person,
    limit: filters.limit,
  };
  if (filters.query_and.length > 0) params['query_and'] = filters.query_and;
  if (filters.query_or.length > 0) params['query_or'] = filters.query_or;

  const res = await api.get<ImageRow[]>('/api/images', { params });
  return res.data;
}

export async function getImageDetail(id: number): Promise<ImageDetail> {
  const res = await api.get<ImageDetail>(`/api/images/${id}`);
  return res.data;
}

export async function getMeta(): Promise<{ cameras: string[]; objects: string[]; persons: string[] }> {
  const [cameras, objects, persons] = await Promise.all([
    api.get<string[]>('/api/meta/cameras'),
    api.get<string[]>('/api/meta/objects'),
    api.get<string[]>('/api/meta/persons'),
  ]);
  return { cameras: cameras.data, objects: objects.data, persons: persons.data };
}

export async function getStats(): Promise<MetaStats> {
  const res = await api.get<MetaStats>('/api/meta/stats');
  return res.data;
}

export function getThumbnailUrl(id: number): string {
  return `/api/media/thumbnail/${id}`;
}

export function getPreviewUrl(id: number): string {
  return `/api/media/preview/${id}`;
}

/** Mirror of filter_panel.py _parse_query() */
export function parseQuery(raw: string): Pick<SearchFilters, 'query_and' | 'query_or'> {
  const s = raw.trim();
  if (s.includes('&')) {
    return {
      query_and: s.split('&').map((t) => t.trim()).filter(Boolean),
      query_or: [],
    };
  }
  if (s.includes(',')) {
    return {
      query_and: [],
      query_or: s.split(',').map((t) => t.trim()).filter(Boolean),
    };
  }
  return {
    query_and: s ? [s] : [],
    query_or: [],
  };
}
