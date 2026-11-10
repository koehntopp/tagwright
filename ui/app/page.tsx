'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Archive, CheckCircle2, Clock, Disc3, Hash, RefreshCw, Search, Settings, TriangleAlert } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { AlbumEdit, CoverDelete, LyricsEdit, SettingsDialog, Shell, TagEditor } from '@/components/dialogs'
import { CopyBtn, CoverImg, IdBadge, Inspector } from '@/components/inspector'
import { DiscogsDialog, MbDialog } from '@/components/releases'
import { Album, Job, LogLine, STATUS, api, post, title } from '@/lib/api'

const FILTERS = [
	{ id: 'all', label: 'All albums', icon: Disc3 },
	{ id: 'needs', label: 'Needs input', icon: TriangleAlert },
	{ id: 'ready', label: 'Ready', icon: Clock },
	{ id: 'fixed', label: 'Fixed', icon: CheckCircle2 },
] as const
const TAGC = ['text-teal-500', 'text-orange-500', 'text-violet-500', 'text-slate-400', 'text-fuchsia-500', 'text-blue-500']
const TONE = { needs: 'bg-rose-100 border-rose-200/70', ready: 'bg-sky-100 border-sky-200/70', fixed: 'bg-emerald-100 border-emerald-200/70' }
const BADGE = { needs: 'bg-rose-600 text-white', ready: 'bg-sky-600 text-white', fixed: 'bg-emerald-600 text-white' }
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
	const [log, setLog] = useState<LogLine[]>([])
	const [dlg, setDlg] = useState<{ kind: string; tab?: string; file?: string; path?: string } | null>(null)
	const [tagTab, setTagTab] = useState<string | null>(null)
	const [cerr, setCerr] = useState('')
	const [kreload, setKreload] = useState(0)
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
		setJob({ state: j.state, path: j.path, queue: j.queue || [] })
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
			setJob({ state: j.state, path: j.path, queue: j.queue || [] })
			addLog(j.lines)
			if (j.state === 'running') tick()
		})()
		const key = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); searchRef.current?.focus() } }
		document.addEventListener('keydown', key)
		return () => document.removeEventListener('keydown', key)
	}, [])  // eslint-disable-line react-hooks/exhaustive-deps

	const count = (s: string) => albums.filter(x => s === 'all' || x.status === s).length
	const artists = useMemo(() => Object.entries(albums.reduce<Record<string, number>>((m, x) => ({ ...m, [x.artist]: (m[x.artist] || 0) + 1 }), {})).filter(([n]) => n).sort((x, y) => y[1] - x[1]).slice(0, 12), [albums])
	const shown = useMemo(() => {
		const s = q.trim().toLowerCase()
		return albums.filter(x => (filter === 'all' || x.status === filter) && (!s || [x.name, x.album, x.artist, x.discogs, x.mbid].some(v => (v || '').toLowerCase().includes(s)))).sort(SORTS[sort])
	}, [albums, filter, q, sort])

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
		try { const r = await post('/api/move', { path: a.path }); addLog(['moved to ' + r.moved_to]); setDlg(null); toast.success('Moved to ingest'); setSelected(null); await load() }
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
	const done = async (path: string) => { await refreshOne(path); setKreload(n => n + 1) }
	const dk = dlg?.kind

	return (
		<div className="flex h-screen overflow-hidden bg-slate-50 text-[14px] text-slate-900">
			<aside className="flex w-64 shrink-0 flex-col gap-4 overflow-y-auto bg-slate-100/80 p-4">
				<div className="flex items-center gap-2 px-2 pt-1 font-serif text-2xl font-semibold tracking-tight">
					<span className="grid size-9 place-items-center rounded-xl bg-white shadow-sm"><Archive className="size-5" /></span>Tagwright
				</div>
				<button onClick={async () => { await load(); toast.success('Rescanned') }} className="flex items-center gap-2 rounded-xl bg-slate-800 px-4 py-3 text-sm font-medium text-white shadow-sm hover:bg-slate-700">
					<RefreshCw className="size-4" /> Rescan folder
				</button>
				<nav className="space-y-1">
					{FILTERS.map(f => (
						<button key={f.id} onClick={() => setFilter(f.id)} className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm ${filter === f.id ? 'bg-white font-medium shadow-sm' : 'text-slate-600 hover:bg-white/60'}`}>
							<f.icon className="size-4 text-orange-500" /><span className="flex-1 text-left">{f.label}</span><span className="text-xs text-slate-400">{count(f.id)}</span>
						</button>
					))}
				</nav>
				<div className="mt-2 px-3 text-xs font-medium uppercase tracking-wider text-slate-500">Artists</div>
				<nav className="space-y-0.5">
					{artists.map(([name, n], i) => (
						<button key={name} onClick={() => setQ(q === name ? '' : name)} className={`flex w-full items-center gap-3 rounded-lg px-3 py-1.5 text-sm ${q === name ? 'bg-white shadow-sm' : 'hover:bg-white/60'}`}>
							<Hash className={`size-4 ${TAGC[i % TAGC.length]}`} /><span className="flex-1 truncate text-left">{name}</span><span className="text-xs text-slate-400">{n}</span>
						</button>
					))}
				</nav>
				<div className="mt-auto space-y-2">
					<div className="flex items-center gap-2 rounded-xl bg-white p-3 text-xs shadow-sm">
						<span className={`size-2 shrink-0 rounded-full ${job.state === 'running' ? 'animate-pulse bg-sky-500' : job.state === 'failed' ? 'bg-rose-500' : job.state === 'stopped' ? 'bg-amber-500' : 'bg-emerald-500'}`} />
						<div className="min-w-0 flex-1 leading-tight">
							<div className="font-medium">Pipeline</div>
							<div className="truncate text-slate-500">
								{job.state === 'running' ? `Running: ${title(albums.find(x => x.path === job.path) || ({ name: '…' } as Album))}${job.queue.length ? ` (+${job.queue.length} queued)` : ''}` : job.state === 'failed' ? 'Last run failed' : job.state === 'stopped' ? 'Last run stopped' : 'Idle'}
							</div>
						</div>
						{job.state === 'running' && <Button size="xs" variant="outline" className="border-rose-300 text-rose-600" onClick={async () => { try { await post('/api/stop', {}); toast.warning('Stopping…') } catch (e: any) { toast.error(e.message) } }}>Stop</Button>}
					</div>
					<button onClick={() => setDlg({ kind: 'settings' })} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-600 hover:bg-white/60"><Settings className="size-4" />Settings</button>
				</div>
			</aside>

			<main className="min-w-0 flex-1 overflow-y-auto p-8">
				<div className="mb-6 flex items-center gap-4">
					<h1 className="text-3xl font-semibold tracking-tight">{FILTERS.find(f => f.id === filter)!.label} <span className="ml-1 text-base font-normal text-slate-400">{shown.length}</span></h1>
					<div className="relative ml-auto w-80">
						<Search className="absolute left-3 top-3 size-4 text-slate-400" />
						<Input ref={searchRef} type="search" value={q} onChange={e => setQ(e.target.value)} placeholder="Search albums, artists, IDs" className="h-10 rounded-xl border-slate-300 bg-white pl-9 pr-12" />
						<kbd className="absolute right-3 top-2.5 rounded bg-slate-100 px-1.5 text-xs text-slate-500">⌘K</kbd>
					</div>
					<select value={sort} onChange={e => setSort(e.target.value)} aria-label="Sort albums" className="h-10 rounded-xl border border-slate-300 bg-white px-3 text-sm">
						<option value="recent">Newest</option><option value="name">Title</option><option value="artist">Artist</option><option value="status">Status</option>
					</select>
				</div>
				{shown.length ? (
					<div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] items-start gap-5">
						{shown.map(x => {
							const ly = x.lyrics
							return (
								<div key={x.path} onClick={() => setSelected(x.path)} className={`cursor-pointer overflow-hidden rounded-2xl border transition hover:-translate-y-0.5 hover:shadow-md ${TONE[x.status]} ${x.path === selected ? 'ring-2 ring-slate-800' : ''}`}>
									<div className="relative aspect-square">
										<CoverImg a={x} className="size-full" />
										<Pill className={`absolute left-3 top-3 shadow ${BADGE[x.status]}`}>{STATUS[x.status]}</Pill>
									</div>
									<div className="space-y-1 p-4">
										<div className="flex min-w-0 items-center gap-1"><h3 className="truncate font-semibold leading-snug">{title(x)}</h3><CopyBtn text={title(x)} /></div>
										<div className="flex min-w-0 items-center gap-1 text-[13px] text-slate-600"><p className="truncate">{x.artist || 'No artist'}{x.year ? ' · ' + x.year : ''}</p>{x.artist && <CopyBtn text={x.artist} />}</div>
										<p className="truncate text-xs text-slate-500">{x.edition || ' '}</p>
										<div className="mt-1 flex min-h-5 flex-nowrap items-center gap-1.5 overflow-hidden">
											{x.discogs && <IdBadge l="D" v={x.discogs} />}
											{x.mbid && <IdBadge l="MB" v={x.mbid} />}
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
						openLyrics={file => setDlg({ kind: 'lyrics', file, path: a.path })} delCover={() => { setCerr(''); setDlg({ kind: 'cover' }) }} putCover={putCover} />
				) : <div className="p-6 text-slate-500">Select an album.</div>}
			</aside>

			<CoverDelete open={dk === 'cover'} onClose={() => setDlg(null)} onOk={delCover} err={cerr} />
			<AlbumEdit a={dk === 'album' ? a : null} onClose={() => setDlg(null)} done={done} />
			<TagEditor a={tagTab ? a : null} tab={tagTab || 'album'} reload={kreload} onClose={() => setTagTab(null)} done={done}
				openLyrics={(path, file) => setDlg({ kind: 'lyrics', path, file })} openDiscogs={() => setDlg({ kind: 'discogs' })} openMb={() => setDlg({ kind: 'mb' })} />
			<LyricsEdit target={dk === 'lyrics' && dlg?.path ? { path: dlg.path, file: dlg.file! } : null} onClose={() => setDlg(null)} done={refreshOne} />
			<Shell open={dk === 'move'} onClose={() => setDlg(null)} title="Move to ingest?" wide="sm:max-w-[24rem]" err={cerr} save={move} saveLabel="Move">
				<p className="text-sm">&ldquo;{a ? title(a) : ''}&rdquo; is moved to the ingest folder.</p>
			</Shell>
			<DiscogsDialog a={dk === 'discogs' ? a : null} onClose={() => setDlg(null)} done={done} />
			<MbDialog a={dk === 'mb' ? a : null} onClose={() => setDlg(null)} done={done} />
			<SettingsDialog open={dk === 'settings'} onClose={() => setDlg(null)} saved={() => { setSelected(null); load('') }} />
		</div>
	)
}
