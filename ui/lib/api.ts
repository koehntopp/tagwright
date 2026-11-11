export type Step = { name: string; done: boolean; partial: boolean; note: string }
export type TrackFile = {
	name: string
	file: string
	title: string
	track: string
	disc: string
	length: number
	dr: string
	lyrics: 'lrc' | 'txt' | 'instr' | 'none'
	checks: boolean[]
}
export type Issue = { text: string; level: string; action?: string }
export type Album = {
	path: string
	name: string
	artist: string
	artist_is_albumartist: boolean
	artist_override: string
	title_override: string
	album: string
	new_title: string
	year: string
	edition: string
	discogs: string
	mbid: string
	dr: string
	mtime: number
	tracks: number
	cover: { w: number; h: number; bytes: number; embedded: boolean } | null
	lyrics: { synced: number; plain: number; instrumental: number; missing: number }
	files: TrackFile[]
	steps: Step[]
	steps_done: number
	issues: Issue[]
	status: 'needs' | 'ready' | 'fixed'
}
export type Job = { state: string; path: string | null; queue: string[]; step?: string }
export type LogLine = { t: string; k: string; m: string }

export async function api<T = any>(u: string, o?: RequestInit): Promise<T> {
	const r = await fetch(u, o)
	if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText)
	return r.json()
}
export const post = <T = any>(u: string, b: unknown) =>
	api<T>(u, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(b) })

export const title = (a: Album) => a.album || a.name
export const mmss = (n: number) => (n ? Math.floor(n / 60) + ':' + String(n % 60).padStart(2, '0') : '')
export const fmtBytes = (n: number) => (n >= 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.round(n / 1024) + ' KB')
export const coverUrl = (a: Album) => `/api/cover?path=${encodeURIComponent(a.path)}&v=${a.mtime}`
export const STATUS = { needs: 'Needs input', ready: 'Ready', fixed: 'Fixed' }

export type Chip = { tag?: string; text?: string; fmt?: string; pad?: number; fallback?: string }
export type Tpl = { folders: Chip[][]; disc_folder: Chip[] | null; filename: Chip[] }
export type LibraryStatus = {
	phase: string; message: string; error: string; artists: number; albums: number; tracks: number
	planned: { from: string; to: string }[]; waiting: number
	unplaced: { path: string; reason: string }[]; skipped: { path: string; reason: string }[]
	recent: { t: number; text: string }[]; last_scan: number; last_full: number
	root: string; apply: boolean; cooldown: number; interval: number
}
