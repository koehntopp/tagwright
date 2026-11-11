'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { RefreshCw, Search, Settings } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { AlbumEdit, CoverDelete, LyricsEdit, SettingsDialog, Shell, TagEditor } from '@/components/dialogs'
import { CopyBtn, CoverImg, IdBadge, Inspector } from '@/components/inspector'
import { LibraryDialog, LibraryIndicator, useLibrary } from '@/components/library'
import { DiscogsDialog, MbDialog } from '@/components/releases'
import { Album, Job, LogLine, STATUS, TrackFile, api, post, title } from '@/lib/api'

const player = typeof Audio !== 'undefined' ? new Audio() : (null as unknown as HTMLAudioElement)

const FILTERS = [
	{ id: 'all', label: 'All albums' },
	{ id: 'needs', label: 'Needs input' },
	{ id: 'ready', label: 'Ready' },
	{ id: 'fixed', label: 'Fixed' },
] as const
const TONE = { needs: 'bg-rose-100 border-rose-200/70', ready: 'bg-sky-100 border-sky-200/70', fixed: 'bg-emerald-100 border-emerald-200/70' }
const BADGE = { needs: 'bg-rose-600 text-white', ready: 'bg-sky-600 text-white', fixed: 'bg-emerald-600 text-white' }
const SORT_KEYS = ['recent', 'name', 'artist', 'status']
const SORT_NAMES: Record<string, string> = { recent: 'Newest', name: 'Title', artist: 'Artist', status: 'Status' }
const ORDER = { needs: 0, ready: 1, fixed: 2 }
const SORTS: Record<string, (a: Album, b: Album) => number> = {
	recent: (a, b) => b.mtime - a.mtime,
	name: (a, b) => title(a).localeCompare(title(b)),
	artist: (a, b) => (a.artist || '').localeCompare(b.artist || '') || title(a).localeCompare(title(b)),
	status: (a, b) => ORDER[a.status] - ORDER[b.status] || title(a).localeCompare(title(b)),
}
const Pill = ({ className = '', ...p }: React.ComponentProps<'span'>) => (
	<span {...p} className={`inline-flex h-5 shrink-0 items-center rounded-full px-2 text-[11px] font-medium ${className}`} />
)

export default function Page() {
	const [albums, setAlbums] = useState<Album[]>([])
	const [filter, setFilter] = useState('all')
	const [q, setQ] = useState('')
	const [sort, setSort] = useState('recent')
	const [selected, setSelected] = useState<string | null>(null)
	const [job, setJob] = useState<Job>({ state: 'idle', path: null, queue: [] })
	const lib = useLibrary()
	const [log, setLog] = useState<LogLine[]>([])
	const [dlg, setDlg] = useState<{ kind: string; tab?: string; file?: string; path?: string } | null>(null)
	const [tagTab, setTagTab] = useState<string | null>(null)
	const [cerr, setCerr] = useState('')
	const [kreload, setKreload] = useState(0)
	const [playing, setPlaying] = useState<string | null>(null)
	const since = useRef(0), ticks = useRef(0), poll = useRef<ReturnType<typeof setTimeout>>(undefined), searchRef = useRef<HTMLInputElement>(null)

	const a = albums.find(x => x.path === selected) || null
	const load = useCallback(async (path = '') => {
		const r = await api('/api/albums' + (path ? '?path=' + encodeURIComponent(path) : ''))
		setAlbums(r.albums)
		return r.albums as Album[]
	}, [])
	const refreshOne = useCallback(async (path: string) => {
		try {
			const s = await api<Album>('/api/album?path=' + encodeURIComponent(path))
			setAlbums(l => l.map(x => (x.path === path ? s : x)))
		} catch {}
	}, [])
	const addLog = (lines: string[]) => {
		setLog(l => [...l, ...lines.map(raw => {
			let t = new Date().toTimeString().slice(0, 8), m = raw
			try { const j = JSON.parse(raw); if (j && j.event) { m = j.event; if (j.timestamp) t = String(j.timestamp).slice(11, 19) || t } } catch {}
			return { t, m, k: /^renamed /.test(m) ? 'file' : /(finished|done|success)/i.test(m) ? 'ok' : '' }
		})])
	}
	const tick = useCallback(async () => {
		clearTimeout(poll.current)
		const j = await api('/api/job?since=' + since.current)
		since.current = j.next
		setJob({ state: j.state, path: j.path, queue: j.queue || [], step: j.step || '' })
		addLog(j.lines)
		if (j.state === 'running') {
			if (++ticks.current % 3 === 0 && j.path) await refreshOne(j.path)
			poll.current = setTimeout(tick, 1000)
		} else {
			await load()
			toast[j.state === 'failed' ? 'error' : j.state === 'stopped' ? 'warning' : 'success'](j.state === 'failed' ? 'Run finished with errors' : j.state === 'stopped' ? 'Run stopped' : 'Run finished')
		}
	}, [load, refreshOne])

	useEffect(() => {
		(async () => {
			await load()
			const j = await api('/api/job?since=0')
			since.current = j.next
			setJob({ state: j.state, path: j.path, queue: j.queue || [], step: j.step || '' })
			addLog(j.lines)
			if (j.state === 'running') tick()
		})()
		player.onended = () => setPlaying(null)
		const key = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); searchRef.current?.focus() } }
		document.addEventListener('keydown', key)
		return () => document.removeEventListener('keydown', key)
	}, [])  // eslint-disable-line react-hooks/exhaustive-deps

	const count = (s: string) => albums.filter(x => s === 'all' || x.status === s).length
	const shown = useMemo(() => {
		const s = q.trim().toLowerCase()
		return albums.filter(x => (filter === 'all' || x.status === filter) && (!s || [x.name, x.album, x.artist, x.discogs, x.mbid].some(v => (v || '').toLowerCase().includes(s)))).sort(SORTS[sort])
	}, [albums, filter, q, sort])

	const cycleSort = () => { const n = SORT_KEYS[(SORT_KEYS.indexOf(sort) + 1) % SORT_KEYS.length]; setSort(n); toast(`Sorted by ${SORT_NAMES[n]}`) }
	const run = async () => {
		if (!a) return
		try {
			await post('/api/run', { paths: [a.path] })
			toast.success(`Running fixes on ${title(a)}…`)
			setJob({ state: 'running', path: a.path, queue: [] }); tick()
		} catch (e: any) { toast.error(e.message) }
	}
	const move = async () => {
		if (!a) return
		try { const r = await post('/api/move', { path: a.path }); addLog(['moved to ' + r.moved_to]); setDlg(null); toast.success('Moved to the library'); setSelected(null); await load() }
		catch (e: any) { setCerr(e.message) }
	}
	const putCover = async (f: File) => {
		if (!a) return
		try {
			const r = await fetch('/api/cover?path=' + encodeURIComponent(a.path), { method: 'PUT', body: f })
			if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText)
			addLog(['cover replaced from ' + f.name]); toast.success('Cover updated'); await refreshOne(a.path)
		} catch (e: any) { toast.error(e.message) }
	}
	const delCover = async () => {
		if (!a) return
		try {
			const r = await fetch('/api/cover?path=' + encodeURIComponent(a.path), { method: 'DELETE' })
			if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText)
			setDlg(null); addLog(['cover removed']); toast.success('Cover removed'); await refreshOne(a.path)
		} catch (e: any) { setCerr(e.message) }
	}
	const play = (f: TrackFile) => {
		if (!a) return
		const key = a.path + '|' + f.file
		if (playing === key) { player.pause(); setPlaying(null); return }
		player.src = `/api/audio?path=${encodeURIComponent(a.path)}&file=${encodeURIComponent(f.file)}`
		player.play().catch(e => { setPlaying(null); toast.error(e.message) })
		setPlaying(key)
	}
	const done = async (path: string) => { await refreshOne(path); setKreload(n => n + 1) }
	const dk = dlg?.kind

	return (
		<div className="flex h-screen flex-col overflow-hidden bg-[#f1f4f9] text-[14px] text-slate-900">
			<header className="flex h-14 shrink-0 items-center gap-2 border-b border-slate-200 bg-[#e9edf3] pl-6">
				<div className="mr-2 flex items-center gap-2 font-serif text-xl font-semibold tracking-tight">
					{/* eslint-disable-next-line @next/next/no-img-element */}
					<img src="/static/icon.svg" alt="" className="size-8 shrink-0" />
				</div>
				<nav className="flex shrink-0 items-center gap-1">
					{FILTERS.map(f => (
						<button key={f.id} onClick={() => (filter === f.id ? cycleSort() : setFilter(f.id))} title={filter === f.id ? `Sorted by ${SORT_NAMES[sort]}; click again to change` : undefined} className={`flex items-center gap-2 rounded-full px-4 py-1.5 text-[17px] font-medium ${filter === f.id ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:bg-white/60'}`}>
						{f.label}<span className="text-sm font-normal text-slate-400">{count(f.id)}</span>
					</button>
				))}
				</nav>
				<button onClick={async () => { await load(); toast.success('Rescanned') }} title="Rescan folder" aria-label="Rescan folder" className="rounded-full p-2 text-slate-600 hover:bg-white/60"><RefreshCw className="size-4" /></button>
				<div className="relative ml-auto w-72 min-w-24 shrink">
					<Search className="absolute left-3 top-2.5 size-4 text-slate-400" />
					<Input ref={searchRef} type="search" value={q} onChange={e => setQ(e.target.value)} placeholder="Search" title="Search albums, artists, IDs (⌘K)" className="h-9 rounded-full border-slate-300 bg-white pl-9 pr-12" />
					<kbd className="absolute right-3 top-2 hidden rounded bg-slate-100 px-1.5 text-xs text-slate-500 min-[1600px]:block">⌘K</kbd>
				</div>
				<button onClick={() => setDlg({ kind: 'settings' })} title="Settings" aria-label="Settings" className="mr-3 shrink-0 rounded-full p-2 text-slate-600 hover:bg-white/60"><Settings className="size-5" /></button>
				<div className="ml-2 flex h-full w-[600px] shrink-0 items-center gap-2 border-l px-4 text-xs">
					<LibraryIndicator st={lib.st} open={() => setDlg({ kind: 'library' })} />
					<div className="h-8 w-px shrink-0 bg-slate-300" />
					<span className={`size-2 shrink-0 rounded-full ${job.state === 'running' ? 'animate-pulse bg-sky-500' : job.state === 'failed' ? 'bg-rose-500' : job.state === 'stopped' ? 'bg-amber-500' : 'bg-emerald-500'}`} />
					<div className="min-w-0 flex-1 leading-tight">
						<div className="font-medium">Pipeline</div>
						<div className="truncate text-slate-500">
							{job.state === 'running' ? `Running: ${title(albums.find(x => x.path === job.path) || ({ name: '…' } as Album))}${job.queue.length ? ` (+${job.queue.length} queued)` : ''}` : job.state === 'failed' ? 'Last run failed' : job.state === 'stopped' ? 'Last run stopped' : 'Idle'}
						</div>
					</div>
					{job.state === 'running' && <Button size="xs" variant="outline" className="border-rose-300 text-rose-600" onClick={async () => { try { await post('/api/stop', {}); toast.warning('Stopping…') } catch (e: any) { toast.error(e.message) } }}>Stop</Button>}
				</div>
			</header>
			<div className="flex min-h-0 flex-1">
			<main className="min-w-0 flex-1 overflow-y-auto p-8">
				{shown.length ? (
					<div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] items-start gap-5">
						{shown.map(x => {
							const ly = x.lyrics
							return (
								<div key={x.path} onClick={() => setSelected(x.path)} className={`cursor-pointer overflow-hidden rounded-2xl border transition hover:-translate-y-0.5 hover:shadow-md ${TONE[x.status]} ${x.path === selected ? 'ring-2 ring-slate-800' : ''}`}>
									<div className="relative aspect-square">
										<CoverImg a={x} className="size-full" />
										<Pill className={`absolute left-3 top-3 shadow ${BADGE[x.status]}`}>{STATUS[x.status]}</Pill>
										{playing?.startsWith(x.path + '|') && (
											<span title="Playing" className="absolute right-3 top-3 flex h-5 items-center gap-0.5 rounded-full bg-yellow-400 px-2.5 shadow">
												{[0, 0.25, 0.5, 0.15].map(d => <i key={d} className="eq-bar block w-0.5 rounded-sm bg-slate-900" style={{ animationDelay: `${d}s` }} />)}
											</span>
										)}
									</div>
									<div className="space-y-1 p-4">
										<div className="flex min-w-0 items-center gap-1"><h3 className="truncate font-semibold leading-snug">{title(x)}</h3><CopyBtn text={title(x)} /></div>
										<div className="flex min-w-0 items-center gap-1 text-[13px] text-slate-600"><p className="truncate">{x.artist || 'No artist'}{x.year ? ' · ' + x.year : ''}</p>{x.artist && <CopyBtn text={x.artist} />}</div>
										<p className="truncate text-xs text-slate-500">{x.edition || ' '}</p>
										<div className="mt-1 flex min-h-6 flex-nowrap items-center gap-1.5 overflow-hidden">
											{x.discogs && <IdBadge l="D" v={x.discogs} />}
											{x.mbid && <IdBadge l="MB" v={x.mbid} />}
										</div>
										<div className="flex min-h-5 flex-nowrap items-center gap-1.5 overflow-hidden">
											{x.dr && <Pill className="bg-white/70 text-emerald-800">DR{x.dr}</Pill>}
											{ly.synced > 0 && <Pill className="bg-emerald-500 text-white">LRC {ly.synced}</Pill>}
											{ly.plain > 0 && <Pill className="bg-amber-400 text-amber-950">TXT {ly.plain}</Pill>}
										</div>
										<div className="mt-2 flex items-center gap-2">
											<Progress value={(x.steps_done / 6) * 100} className="h-1.5 flex-1 bg-white/70" />
											<span className="text-xs tabular-nums text-slate-500">{x.steps_done}/6</span>
										</div>
									</div>
								</div>
							)
						})}
					</div>
				) : <div className="py-16 text-center text-slate-500">No albums match.</div>}
			</main>
			<aside className="w-[600px] shrink-0 overflow-y-auto border-l bg-white">
				{a ? (
					<Inspector key={a.path} a={a} job={job} log={log} refresh={() => refreshOne(a.path)} run={run} move={() => { setCerr(''); setDlg({ kind: 'move' }) }}
						openEditor={tab => setTagTab(tab)} openAlbum={() => setDlg({ kind: 'album' })} openDiscogs={() => setDlg({ kind: 'discogs' })} openMb={() => setDlg({ kind: 'mb' })}
						openLyrics={file => setDlg({ kind: 'lyrics', file, path: a.path })} playing={playing} play={play} delCover={() => { setCerr(''); setDlg({ kind: 'cover' }) }} putCover={putCover} />
				) : <div className="p-6 text-slate-500">Select an album.</div>}
			</aside>
			</div>

			<CoverDelete open={dk === 'cover'} onClose={() => setDlg(null)} onOk={delCover} err={cerr} />
			<AlbumEdit a={dk === 'album' ? a : null} onClose={() => setDlg(null)} done={done} />
			<TagEditor a={tagTab ? a : null} tab={tagTab || 'album'} reload={kreload} onClose={() => setTagTab(null)} done={done}
				openLyrics={(path, file) => setDlg({ kind: 'lyrics', path, file })} openDiscogs={() => setDlg({ kind: 'discogs' })} openMb={() => setDlg({ kind: 'mb' })} />
			<LyricsEdit target={dk === 'lyrics' && dlg?.path ? { path: dlg.path, file: dlg.file! } : null} onClose={() => setDlg(null)} done={refreshOne} />
			<Shell open={dk === 'move'} onClose={() => setDlg(null)} title="Move to the library?" wide="sm:max-w-[24rem]" err={cerr} save={move} saveLabel="Move">
				<p className="text-sm">&ldquo;{a ? title(a) : ''}&rdquo; is placed in the library folder, each track in its folder and under its name from the layout.</p>
			</Shell>
			<DiscogsDialog a={dk === 'discogs' ? a : null} onClose={() => setDlg(null)} done={done} />
			<MbDialog a={dk === 'mb' ? a : null} onClose={() => setDlg(null)} done={done} />
			<LibraryDialog open={dk === 'library'} onClose={() => setDlg(null)} st={lib.st} reload={lib.reload} />
			<SettingsDialog open={dk === 'settings'} onClose={() => setDlg(null)} saved={() => { setSelected(null); load('') }} />
		</div>
	)
}
