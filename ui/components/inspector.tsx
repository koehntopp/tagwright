'use client'

import { useEffect, useRef, useState } from 'react'
import { ChartColumn, Check, ChevronDown, Copy, Ellipsis, Fingerprint, FileText, Loader2, Mic, ClipboardPaste, Pause, Pencil, Play, RefreshCw, Tags, Trash2, OctagonX, TriangleAlert, Upload, Volume2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { flagOf } from '@/lib/flags'
import { Album, CoverItem, Covers, Job, LogLine, TrackFile, api, channelLabel, coverUrl, fmtBytes, mmss, title } from '@/lib/api'

// navigator.clipboard exists only in secure contexts (https or localhost); over plain http on the LAN the
// textarea and execCommand route is the one that works.
function copyViaTextarea(text: string): boolean {
	const t = document.createElement('textarea')
	t.value = text
	t.style.position = 'fixed'
	t.style.opacity = '0'
	;(document.querySelector('[role=dialog]') ?? document.body).appendChild(t) // inside an open dialog: the rest of the page is inert
	t.select()
	try { return document.execCommand('copy') } catch { return false } finally { t.remove() }
}
export function copy(text: string) {
	const done = () => toast.success('Copied'), fail = () => toast.error('Copy failed')
	if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, () => (copyViaTextarea(text) ? done() : fail()))
	else if (copyViaTextarea(text)) done()
	else fail()
}
export const CopyBtn = ({ text, title = 'Copy' }: { text: string; title?: string }) => (
	<button
		onClick={e => { e.stopPropagation(); copy(text) }}
		title={title}
		className="shrink-0 rounded-full p-1 text-slate-400 hover:bg-black/5 hover:text-slate-700"
	>
		<Copy className="size-3" />
	</button>
)

export const LY = {
	lrc: ['LRC', 'bg-emerald-500 text-white', 'Synced lyrics (LRC)'],
	txt: ['TXT', 'bg-amber-400 text-amber-950', 'Plain text lyrics, not synced'],
	instr: ['INS', 'bg-sky-100 text-sky-800', 'Instrumental'],
	none: ['---', 'bg-rose-100 text-rose-700', 'No lyrics'],
} as const

export const Pill = ({ className = '', ...p }: React.ComponentProps<'span'>) => (
	<span {...p} className={`inline-flex h-5 items-center justify-center rounded-full px-2 text-[11px] font-medium ${className}`} />
)

type CoverKind = 'front' | 'back' | 'leaflet' | 'media'
const COVER_TYPE: Record<CoverKind, number> = { front: 3, back: 4, leaflet: 5, media: 6 }

/** One of the four artwork fields of the inspector (ADR 0090). Front is single; the others are small carousels. */
function CoverField({ kind, label, items, fallback, fallbackSize, warn, busy, put, remove, askRemove, inputRef, rootRef, search, paste, menuOpen, toggleMenu, onEnlarge }: {
	kind: CoverKind
	label: string
	items: CoverItem[]
	fallback?: string
	fallbackSize?: string
	warn?: string
	busy: boolean
	put: (file: File, index?: number) => void
	remove: (index: number) => void
	askRemove: () => void
	inputRef?: React.RefObject<HTMLInputElement | null>
	rootRef?: React.RefObject<HTMLDivElement | null>
	search?: React.ReactNode
	paste?: () => void
	onEnlarge?: (url: string) => void
	menuOpen?: boolean
	toggleMenu?: () => void
}) {
	const multiple = kind !== 'front'
	const [sel, setSel] = useState(0)
	const mode = useRef<'add' | 'replace'>('add')
	const ownInput = useRef<HTMLInputElement>(null)
	const input = inputRef ?? ownInput
	const [drag, setDrag] = useState(false)
	const at = items.length ? Math.min(sel, items.length - 1) : 0
	const current = items[at] ?? null
	const pick = (m: 'add' | 'replace') => { mode.current = m; input.current?.click() }
	const sendFile = (f?: File) => {
		if (!f) return
		if (!f.type.startsWith('image/')) { toast.error('That is not an image'); return }
		put(f, mode.current === 'replace' && current ? at : undefined)
	}
	const step = (d: number) => setSel((at + d + items.length) % items.length)
	// Cmd/Ctrl+V on the focused field (ADR 0096): the front cover is replaced, the other types get the image appended
	const onPaste = (e: React.ClipboardEvent) => {
		const f = [...e.clipboardData.files].find(f => f.type.startsWith('image/'))
		if (f) { e.preventDefault(); put(f) } else toast.error('No image on the clipboard')
	}
	return (
		<div ref={rootRef} tabIndex={-1} data-cover-menu={kind === 'front' ? '' : undefined} onPaste={onPaste}
			onDragOver={e => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
			onDrop={e => {
				e.preventDefault(); setDrag(false)
				const f = [...e.dataTransfer.files][0]
				mode.current = current ? 'replace' : 'add'
				sendFile(f)
			}}
			title={warn}
			className={`relative flex min-h-[9rem] flex-col rounded-xl border p-2 outline-none ${warn ? 'border-amber-400 bg-amber-50' : drag ? 'ring-4 ring-slate-800' : 'border-slate-200 bg-slate-50'}`}>
			<div className="flex items-center justify-between gap-1">
				<span className="truncate text-xs font-medium text-slate-700">{label}{warn && <TriangleAlert className="ml-1 inline size-3 text-amber-700" />}</span>
				<span className="flex shrink-0 items-center gap-1">
					{(current || fallback) && <span className="text-[10px] tabular-nums text-slate-500" title={current ? `${current.w}×${current.h}, ${fmtBytes(current.bytes)}` : undefined}>{current ? `${current.w}×${current.h}` : fallbackSize}</span>}
					{multiple && items.length > 0 && <span className="text-[11px] tabular-nums text-slate-500">{at + 1}/{items.length}</span>}
				</span>
			</div>
			<div className="relative mt-1 aspect-square w-full overflow-hidden rounded-lg bg-white/70">
				{current ? (
					// eslint-disable-next-line @next/next/no-img-element
					<img src={current.url} alt={label} title={`${current.w}×${current.h}, ${fmtBytes(current.bytes)} — double-click to view full size`} onDoubleClick={() => onEnlarge?.(current.url)} className="absolute inset-0 size-full cursor-zoom-in object-cover" />
				) : fallback ? (
					// eslint-disable-next-line @next/next/no-img-element
					<img src={fallback} alt={label} title="Double-click to view full size" onDoubleClick={() => onEnlarge?.(fallback)} className="absolute inset-0 size-full cursor-zoom-in object-cover opacity-70" />
				) : <span className="absolute inset-0 grid place-items-center px-1 text-center text-[11px] leading-tight text-slate-400">Drop image or click Upload</span>}
				{busy && <div className="absolute inset-0 grid place-items-center bg-white/70"><Loader2 className="size-5 animate-spin text-slate-700" /></div>}
			</div>
			<div className="mt-1 flex items-center gap-0.5">
				{multiple && <>
					<button type="button" title="Previous image" aria-label="Previous image" disabled={items.length < 2} onClick={() => step(-1)} className="rounded px-1 text-slate-600 hover:bg-white disabled:opacity-30">‹</button>
					<button type="button" title="Next image" aria-label="Next image" disabled={items.length < 2} onClick={() => step(1)} className="rounded px-1 text-slate-600 hover:bg-white disabled:opacity-30">›</button>
				</>}
				{!current && !fallback && <button type="button" onClick={() => pick('add')} className="shrink-0 whitespace-nowrap rounded px-1.5 text-[11px] text-slate-700 hover:bg-white">Upload</button>}
				{(current || fallback) && <button type="button" onClick={() => current ? remove(at) : askRemove()} className="shrink-0 whitespace-nowrap rounded px-1.5 text-[11px] text-rose-600 hover:bg-rose-50">Delete</button>}
				{multiple && <button type="button" title="Add an image" onClick={() => pick('add')} className="shrink-0 whitespace-nowrap rounded px-1.5 text-[11px] text-slate-700 hover:bg-white">+</button>}
				{kind === 'front' && toggleMenu && <button type="button" onClick={toggleMenu} aria-label="Cover options" aria-expanded={menuOpen} className="ml-auto shrink-0 rounded p-0.5 text-slate-500 hover:bg-white"><Ellipsis className="size-3.5" /></button>}
			</div>
			<input ref={input} type="file" accept="image/*" className="hidden" onChange={e => { sendFile(e.target.files?.[0]); e.target.value = '' }} />
			{menuOpen && search && (
				<div role="menu" className="absolute bottom-8 right-1 z-20 w-56 rounded-lg border bg-white p-1 text-sm shadow-md">
					<button role="menuitem" className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-slate-100" onClick={() => { toggleMenu?.(); pick('replace') }}><Upload className="size-4" />Upload image</button>
					<button role="menuitem" className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-slate-100" onClick={() => { toggleMenu?.(); paste?.() }}><ClipboardPaste className="size-4" />Paste image</button>
					{search}
					<button role="menuitem" className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-rose-600 hover:bg-rose-50" onClick={() => { toggleMenu?.(); askRemove() }}><Trash2 className="size-4" />Remove cover</button>
				</div>
			)}
		</div>
	)
}

/** Which disc's artwork the cover fields edit (ADR 0098): a pill as wide as the cover grid; when the discs do not
 * fit, it scrolls sideways and shows ‹ › buttons at its ends. */
function DiscSwitch({ discs, disc, choose }: { discs: number[]; disc?: number; choose: (disc?: number) => void }) {
	const strip = useRef<HTMLDivElement>(null)
	const [edges, setEdges] = useState({ left: false, right: false })
	const measure = () => {
		const el = strip.current
		if (el) setEdges({ left: el.scrollLeft > 1, right: el.scrollLeft + el.clientWidth < el.scrollWidth - 1 })
	}
	useEffect(() => {
		const el = strip.current
		if (!el) return
		const ro = new ResizeObserver(measure)
		ro.observe(el)
		return () => ro.disconnect()
	}, [discs.length])
	useEffect(() => { strip.current?.querySelector('[aria-pressed="true"]')?.scrollIntoView({ block: 'nearest', inline: 'nearest' }) }, [disc])
	const by = (d: number) => strip.current?.scrollBy({ left: d * strip.current.clientWidth * 0.6, behavior: 'smooth' })
	const arrow = 'grid h-full w-6 shrink-0 place-items-center rounded-full text-slate-500 hover:bg-slate-100 hover:text-slate-800 disabled:opacity-30'
	return (
		<div className="flex items-center gap-2 text-xs text-slate-500">
			<span className="shrink-0">Artwork for</span>
			<div role="group" aria-label="Artwork for" className="flex h-7 min-w-0 flex-1 items-center rounded-full border border-slate-300 bg-white p-0.5">
				{(edges.left || edges.right) && <button type="button" aria-label="Earlier discs" title="Earlier discs" disabled={!edges.left} onClick={() => by(-1)} className={arrow}>‹</button>}
				<div ref={strip} onScroll={measure} className="flex h-full min-w-0 flex-1 items-center overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
					{[undefined, ...discs].map(d => (
						<button key={d ?? 'all'} type="button" aria-pressed={disc === d} onClick={() => choose(d)}
							className={`h-full shrink-0 whitespace-nowrap rounded-full px-2.5 ${disc === d ? 'bg-slate-200 text-slate-900' : 'text-slate-500 hover:text-slate-800'}`}>
							{d === undefined ? 'All discs' : `Disc ${d}`}
						</button>
					))}
				</div>
				{(edges.left || edges.right) && <button type="button" aria-label="Later discs" title="Later discs" disabled={!edges.right} onClick={() => by(1)} className={arrow}>›</button>}
			</div>
		</div>
	)
}

/** Channel layout of a track: Mono and Stereo neutral, multichannel violet (ADR 0040). `hint`: taken from a title. */
export function ChannelBadge({ n, hint }: { n?: number; hint?: boolean }) {
	if (!n) return null
	return <span title={hint ? `The title says ${channelLabel(n)}` : `${n} channel${n > 1 ? 's' : ''}`} className={`inline-flex h-5 w-[3.25rem] shrink-0 items-center justify-center rounded-full text-[11px] font-medium ${n > 2 ? 'bg-violet-100 text-violet-800' : 'bg-slate-200 text-slate-700'} ${hint ? 'opacity-70' : ''}`}>{channelLabel(n)}</span>
}

export const searchQuery = (a: Album) => [a.artist, title(a)].filter(Boolean).join(' ')

/** The ID of a release on Discogs or MusicBrainz; without one, a link that searches the site for `q` (artist and title as they are now). */
export const IdBadge = ({ l, v, full, q }: { l: 'D' | 'MB'; v: string; full?: boolean; q?: string }) => {
	const icon = l === 'D' ? '/static/discogs.png' : '/static/musicbrainz.ico'
	const url = (l === 'D' ? 'https://www.discogs.com/release/' : 'https://musicbrainz.org/release/') + encodeURIComponent(v)
	return v ? (
		<a href={url} target="_blank" rel="noopener" onClick={e => e.stopPropagation()} className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 font-mono text-[11px] hover:bg-slate-200">
			{/* eslint-disable-next-line @next/next/no-img-element */}
			<img src={icon} alt={l} className="size-3.5 rounded-sm" />
			{!full && v.length > 13 ? v.slice(0, 8) : v}
		</a>
	) : q ? (
		<a href={(l === 'D' ? 'https://www.discogs.com/search?type=all&q=' : 'https://musicbrainz.org/search?type=release&method=indexed&query=') + encodeURIComponent(q)}
			target="_blank" rel="noopener" onClick={e => e.stopPropagation()} title={`Search ${l === 'D' ? 'Discogs' : 'MusicBrainz'} for ${q}`}
			className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2 py-0.5 text-[11px] font-medium text-rose-700 hover:bg-rose-200">
			{/* eslint-disable-next-line @next/next/no-img-element */}
			<img src={icon} alt={l} className="size-3.5 rounded-sm" />missing
		</a>
	) : (
		<Pill className="gap-1 bg-rose-100 text-rose-700">
			{/* eslint-disable-next-line @next/next/no-img-element */}
			<img src={icon} alt={l} className="size-3.5 rounded-sm" />missing
		</Pill>
	)
}

export function CoverImg({ a, className = '' }: { a: Album; className?: string }) {
	const hue = [...(a.artist || a.name)].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7)
	const initials = (a.artist || a.name || '?').split(/\s+/).map(w => w[0]).slice(0, 2).join('').toUpperCase()
	return (
		<div className={`relative overflow-hidden ${className}`} style={{ background: `linear-gradient(135deg,hsl(${hue} 70% 62%),hsl(${(hue + 40) % 360} 60% 30%))` }}>
			<span className="absolute inset-0 grid place-items-center text-3xl font-bold text-white/80">{initials}</span>
			{a.cover && (
				// eslint-disable-next-line @next/next/no-img-element
				<img src={coverUrl(a)} alt="" loading="lazy" className="absolute inset-0 size-full object-cover" onError={e => e.currentTarget.remove()} />
			)}
		</div>
	)
}

type Props = {
	a: Album
	job: Job
	log: LogLine[]
	refresh: () => void
	run: (step?: string) => void
	working?: string[]  // steps a save is rewriting right now (not a pipeline job)
	move: () => void
	inLibrary?: boolean
	openEditor: (tab: string) => void
	openAlbum: () => void
	openDiscogs: () => void
	openMb: () => void
	openLyrics: (file: string) => void
	playing: string | null
	play: (f: TrackFile) => void
	delCover: () => void  // front cover, with confirmation
	delArtwork: (type: number, index: number) => void
	putCover: (f: File, type?: number, index?: number) => void
	coverBusy?: boolean  // a cover is being processed (scaled and embedded)
	coverTick: number
	coverDisc?: number  // the disc the cover fields show and edit; undefined: all discs (ADR 0098)
	setCoverDisc: (disc?: number) => void
}

const STEP_ICON: Record<string, typeof Check> = { 'Dynamic range': ChartColumn, ReplayGain: Volume2, Fingerprints: Fingerprint, 'Tags and cover': Tags, Lyrics: Mic, Filenames: FileText }
const OPTIONAL_STEP = 'Lyrics'  // ADR 0054

const TONES = {
	error: ['border-rose-200 bg-rose-50 text-rose-900', 'text-rose-700'],
	warn: ['border-amber-200 bg-amber-50 text-amber-900', 'text-amber-700'],
	info: ['border-sky-200 bg-sky-50 text-sky-900', 'text-sky-700'],
} as const

// One box for every note of the inspector: the type (with a stop symbol for a problem, a warning sign for the rest)
// at the left, the lines beside it, the action button at the right.
function NoteBox({ tone, label, action, children }: { tone: keyof typeof TONES; label: string; action?: React.ReactNode; children: React.ReactNode }) {
	const [box, head] = TONES[tone]
	const Icon = tone === 'error' ? OctagonX : TriangleAlert
	return (
		<div className={`flex items-start gap-3 rounded-xl border px-3 py-1.5 text-[13px] ${box}`}>
			<div className={`flex w-32 shrink-0 items-center gap-1.5 text-xs font-medium uppercase leading-5 tracking-wider ${head}`}><Icon className="size-3.5 shrink-0" />{label}</div>
			<div className="min-w-0 flex-1 space-y-0.5 leading-5">{children}</div>
			{action || null}
		</div>
	)
}

// An album's line in the folder box: the title and its version string (left out when the title holds it already)
const versionLine = (album: string, version: string) => album + (version && !album.includes(version) ? ' ' + version : '')

export function Inspector(p: Props) {
	const { a, job } = p
	const [stepSel, setStep] = useState<number | null>(null)
	const [tracksOpen, setTracksOpen] = useState(true)
	const [logOpen, setLogOpen] = useState(false)
	const [menu, setMenu] = useState(false)  // the front cover's menu
	const [big, setBig] = useState<string | null>(null)  // full-size cover modal (ADR 0092)
	useEffect(() => {
		if (!big) return
		const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setBig(null) }
		document.addEventListener('keydown', esc)
		return () => document.removeEventListener('keydown', esc)
	}, [big])
	const [covers, setCovers] = useState<Covers>({ front: [], back: [], leaflet: [], media: [] })
	useEffect(() => {
		let live = true
		const empty: Covers = { front: [], back: [], leaflet: [], media: [] }
		const disc = p.coverDisc !== undefined ? '&disc=' + p.coverDisc : ''
		api<Covers>('/api/covers?path=' + encodeURIComponent(a.path) + disc).then(r => live && setCovers(r), () => live && setCovers(empty))
		return () => { live = false }
	}, [a.path, a.mtime, p.coverTick, p.coverDisc])
	useEffect(() => {
		if (!menu) return
		const close = (e: Event) => { if (!(e.target as Element).closest?.('[data-cover-menu]')) setMenu(false) }
		const esc = (e: KeyboardEvent) => e.key === 'Escape' && setMenu(false)
		document.addEventListener('mousedown', close); document.addEventListener('keydown', esc)
		return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc) }
	}, [menu])
	const fileRef = useRef<HTMLInputElement>(null)
	const coverRef = useRef<HTMLDivElement>(null)
	// "Paste image" (ADR 0016): read the clipboard where the browser allows it (https, localhost); over plain http on
	// the LAN there is no clipboard API, so the cover takes focus and the paste key (Cmd/Ctrl+V) delivers the image
	const pasteCover = async (ref?: React.RefObject<HTMLDivElement | null>) => {
		const fail = () => toast.error('No image on the clipboard')
		if (!navigator.clipboard?.read) { (ref ?? coverRef).current?.focus(); toast.info('Press Cmd/Ctrl+V to paste the image'); return }
		try {
			for (const item of await navigator.clipboard.read()) {
				const type = item.types.find(t => t.startsWith('image/'))
				if (type) return p.putCover(new File([await item.getType(type)], 'pasted.' + type.split('/')[1], { type }))
			}
			fail()
		} catch { fail() }
	}
	// non-consequential notes where MusicBrainz and Discogs disagree (selected album only: one cached MusicBrainz lookup)
	const [mbNotes, setMbNotes] = useState<string[]>([])
	const [mbMismatch, setMbMismatch] = useState<string[]>([])  // the year differs: stops the move (ADR 0083)
	useEffect(() => {
		setMbNotes([]); setMbMismatch([])
		if (!a.discogs || !a.mbid) return
		let live = true
		api<{ notes: string[]; mismatches: string[] }>('/api/musicbrainz/check?path=' + encodeURIComponent(a.path)).then(r => { if (live) { setMbNotes(r.notes); setMbMismatch(r.mismatches) } }, () => {})
		return () => { live = false }
	}, [a.path, a.discogs, a.mbid, a.mtime])
	// other versions of this album's Discogs master in the library (ADR 0082)
	const [versions, setVersions] = useState<{ path: string; album: string; version: string }[]>([])
	useEffect(() => {
		setVersions([])
		if (!a.master) return
		let live = true
		api<{ versions: typeof versions }>('/api/library/versions?path=' + encodeURIComponent(a.path)).then(r => live && setVersions(r.versions), () => {})
		return () => { live = false }
	}, [a.path, a.master, a.mtime])
	const running = job.state === 'running' && job.path === a.path
	const spinning = (name: string) => (running && name === job.step) || !!p.working?.includes(name)

	const coverSmall = a.issues.some(i => i.action === 'cover')  // below the minimum size, or no cover (ADR 0016)
	return (
		<div className="space-y-5 p-6">
			<div className="min-w-0 space-y-1">
					<div className="flex items-center gap-1 text-xs text-slate-500">
						<span className="truncate" title={a.artist_is_albumartist ? '' : 'from ARTIST tag'}>{a.artist || 'No artist'}</span>
						<button onClick={p.openAlbum} title="Edit album artist and title"><Pencil className="size-3" /></button>
						{a.artist && <CopyBtn text={a.artist} />}
					</div>
					<h2 className="text-xl font-semibold leading-tight">
						{title(a)}
						<button onClick={p.openAlbum} className="ml-1 align-middle" title="Edit album artist and title"><Pencil className="inline size-3" /></button>
						<CopyBtn text={title(a)} />
					</h2>
					<div className="mt-0.5 text-xs text-slate-500" title={a.country || undefined}>
						{/* the version string already holds year, DR, format and catalogue number: nothing is shown twice */}
						{flagOf(a.country) && <span className="mr-1">{flagOf(a.country)}</span>}
						{a.version || [a.year, a.media || 'CD', a.catalog].filter(Boolean).join(' · ')}
						{a.catalog && a.catalog.toLowerCase() !== 'none' && <span className="inline-flex align-middle"><CopyBtn text={a.catalog} title="Copy the catalogue number" /></span>}
					</div>
					<div className="mt-2 flex flex-wrap items-center gap-1">
						<IdBadge l="D" v={a.discogs} q={searchQuery(a)} />
						<button onClick={p.openDiscogs} title="Change the Discogs release" className="mr-1"><Pencil className="size-3" /></button>
						<IdBadge l="MB" v={a.mbid} q={searchQuery(a)} />
						<button onClick={p.openMb} title="Choose the MusicBrainz release" className="mr-1"><Pencil className="size-3" /></button>
						{a.dr && <Pill className="bg-emerald-100 text-emerald-800" title="Album dynamic range">DR{a.dr}</Pill>}
					</div>
			</div>
			{(covers.discs?.length ?? 0) > 1 && <DiscSwitch discs={covers.discs ?? []} disc={p.coverDisc} choose={p.setCoverDisc} />}
			<div className="grid grid-cols-4 gap-2">
				<CoverField kind="front" label="Front Cover" items={covers.front}
					fallback={p.coverDisc === undefined && !covers.front.length && a.cover && !a.cover.embedded ? coverUrl(a) : undefined}
					fallbackSize={a.cover ? `${a.cover.w}×${a.cover.h}` : undefined}
					warn={coverSmall ? a.issues.find(i => i.action === 'cover')?.text : undefined} busy={!!p.coverBusy}
					put={(f, i) => p.putCover(f, COVER_TYPE.front, i)} remove={p.delCover} askRemove={p.delCover}
					inputRef={fileRef} rootRef={coverRef}
					menuOpen={menu} toggleMenu={() => setMenu(m => !m)} paste={() => void pasteCover(coverRef)} onEnlarge={url => setBig(url)}
					search={<>
						<a role="menuitem" className="flex items-center gap-2 rounded px-2 py-1.5 hover:bg-slate-100" onClick={() => setMenu(false)} href={`https://covers.musichoarders.xyz/?${new URLSearchParams({ artist: a.artist || '', album: title(a) })}`} target="_blank" rel="noopener">
							{/* eslint-disable-next-line @next/next/no-img-element */}
							<img src="/static/musichoarders.svg" alt="" className="size-4 rounded-sm bg-slate-800 p-px" />Search musichoarders
						</a>
						<a role="menuitem" className="flex items-center gap-2 rounded px-2 py-1.5 hover:bg-slate-100" onClick={() => setMenu(false)} href={`https://albumartexchange.com/covers?${new URLSearchParams({ q: [a.artist, title(a)].filter(Boolean).join(' '), fltr: 'ALL', sort: 'SCORE', status: '', size: 'any' })}`} target="_blank" rel="noopener">
							{/* eslint-disable-next-line @next/next/no-img-element */}
							<img src="/static/albumartexchange.ico" alt="" className="size-4 rounded-sm" />Search albumartexchange
						</a>
					</>} />
				<CoverField kind="back" label="Back Cover" items={covers.back} busy={!!p.coverBusy}
					put={(f, i) => p.putCover(f, COVER_TYPE.back, i)} remove={i => p.delArtwork(COVER_TYPE.back, i)} askRemove={() => {}} onEnlarge={url => setBig(url)} />
				<CoverField kind="leaflet" label="Leaflet" items={covers.leaflet} busy={!!p.coverBusy}
					put={(f, i) => p.putCover(f, COVER_TYPE.leaflet, i)} remove={i => p.delArtwork(COVER_TYPE.leaflet, i)} askRemove={() => {}} onEnlarge={url => setBig(url)} />
				<CoverField kind="media" label="Media" items={covers.media} busy={!!p.coverBusy}
					put={(f, i) => p.putCover(f, COVER_TYPE.media, i)} remove={i => p.delArtwork(COVER_TYPE.media, i)} askRemove={() => {}} onEnlarge={url => setBig(url)} />
			</div>
			<div className="flex gap-2">
				<Button className="flex-1 bg-slate-800 text-white hover:bg-slate-700" onClick={() => p.openEditor('album')}>Tag Editor</Button>
				<Button className={`flex-1 ${running ? 'border-rose-600 bg-rose-600 text-white disabled:opacity-100' : ''}`} variant="outline" disabled={a.status === 'needs' || job.state === 'running'} onClick={() => p.run()}>{running ? 'Running…' : 'Run fixes'}</Button>
				<Button className="flex-1" variant="outline" disabled={p.inLibrary || a.status !== 'fixed' || a.issues.some(i => i.level === 'ingest') || mbMismatch.length > 0 || job.state === 'running'} title={p.inLibrary ? 'This album is already in the library' : mbMismatch.length ? `${mbMismatch[0]} Fix the release before moving.` : undefined} onClick={p.move}>Move to library</Button>
			</div>

			{a.issues.map(i => (
				<NoteBox key={i.text} tone={i.level === 'error' ? 'error' : i.level === 'info' ? 'info' : 'warn'} label={i.level === 'error' ? 'Problem' : i.level === 'info' ? 'Note' : 'Warning'}
					action={i.action && (
						<Button size="xs" variant="outline" onClick={() => ({ search: p.openDiscogs, album: () => p.openEditor('album'), tracks: () => p.openEditor('tracks'), cover: () => fileRef.current?.click() } as Record<string, () => void>)[i.action!]()}>
							{{ search: 'Search', album: 'Tag Editor', tracks: 'Tag Editor', cover: 'Upload' }[i.action]}
						</Button>
					)}>
					{i.text}
				</NoteBox>
			))}

			{mbMismatch.length > 0 && (
				<NoteBox tone="error" label="Mismatch" action={<Button size="xs" variant="outline" onClick={p.openMb}>MusicBrainz</Button>}>
					{mbMismatch.map(n => <div key={n}>{n}</div>)}
				</NoteBox>
			)}

			{([[false, 'Missing', 'error'], [true, 'Optional', 'info']] as const).map(([opt, title, tone]) => {
				const items = (a.missing ?? []).filter(m => !!m.optional === opt)
				const holdsRun = opt ? !(a.missing ?? []).some(m => !m.optional) : true  // Run fixes sits on the first of the two boxes
				return !!items.length && (
					<NoteBox key={title} tone={tone} label={title}
						action={holdsRun && <Button size="xs" variant="outline" disabled={a.status === 'needs' || job.state === 'running'} title="Run the pipeline for the missing data" onClick={() => p.run()}>Run fixes</Button>}>
						{items.map(m => (
							<div key={m.step}>
								<button className="w-full text-left hover:underline" title="Mark these tracks in the track list" onClick={() => { setStep(a.steps.findIndex(s => s.name === m.step)); setTracksOpen(true) }}>
									<span className="font-medium">{m.label}</span> on {m.count === m.of ? `all ${m.of} tracks` : `${m.count} of ${m.of} tracks`}
								</button>
							</div>
						))}
					</NoteBox>
				)
			})}

			{mbNotes.length > 0 && (
				<NoteBox tone="info" label="Note" action={<Button size="xs" variant="outline" onClick={p.openMb}>MusicBrainz</Button>}>
					{mbNotes.map(n => <div key={n}>{n}</div>)}
				</NoteBox>
			)}

			<div className="space-y-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-[13px] text-slate-800">
				{([
					['Current folder', [<code key="c" className="break-all text-xs">{a.folder || a.name}</code>]],
					['New folder', a.new_title ? [<code key="n" className="break-all text-xs">{a.new_title}</code>, <span key="t" className="block break-words text-xs">{versionLine(a.album || a.name, a.version)}</span>] : [<span key="n" className="text-xs text-slate-400">Not ready: artist or album is empty</span>]],
					...(versions.length > 0 ? [['In your library', versions.map(v => <span key={v.path} className="block break-words text-xs" title={v.path}>{versionLine(v.album, v.version)}</span>)] as const] : []),
				] as const).map(([label, lines]) => (
					<div key={label} className="flex items-baseline gap-3">
						<div className="w-32 shrink-0 text-xs font-medium uppercase tracking-wider text-slate-500">{label}</div>
						<div className="min-w-0 flex-1 space-y-0.5">{lines}</div>
					</div>
				))}
			</div>

			<div>
				<h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-500">Pipeline</h4>
				<ol className="grid grid-cols-6 gap-1 text-center text-[11px] leading-tight">
					{a.steps.map((s, i) => {
						const Icon = STEP_ICON[s.name] ?? Check, busy = spinning(s.name)
						return (
							<li key={s.name} title={(s.note ? s.note + ' ' : '') + 'Double-click to run only this step.'} className="relative cursor-pointer select-none" onClick={() => { setStep(stepSel === i ? null : i); setTracksOpen(true) }} onDoubleClick={() => { if ((a.status !== 'needs' || ['Dynamic range', 'ReplayGain', 'Fingerprints'].includes(s.name)) && job.state !== 'running') p.run(s.name) }}>
								{i > 0 && <span aria-hidden className="absolute right-1/2 top-[17px] -z-0 h-0.5 w-full bg-slate-200" />}
								<div className={`relative z-10 mx-auto mb-1 grid size-9 place-items-center rounded-full ${busy ? 'bg-sky-500 text-white ring-2 ring-sky-300' : s.done ? (s.partial ? 'bg-amber-400 text-amber-950' : 'bg-emerald-500 text-white') : `border bg-white text-slate-400 ${s.name === OPTIONAL_STEP ? 'border-dashed' : ''}`}`}>
									{busy ? <RefreshCw className="size-[18px] animate-spin" /> : <Icon className="size-[18px]" />}
									{!busy && s.done && (
										<span className={`absolute -bottom-0.5 -right-0.5 grid size-[15px] place-items-center rounded-full border-[1.5px] border-white text-white ${s.partial ? 'bg-amber-700' : 'bg-emerald-700'}`}>
											{s.partial ? <TriangleAlert className="size-2.5" /> : <Check className="size-2.5" />}
										</span>
									)}
								</div>
								<span className={`rounded px-1 ${stepSel === i ? 'bg-slate-800/10 font-medium' : ''}`}>{s.name.replace(' and ', ' & ')}</span>
							</li>
						)
					})}
				</ol>
			</div>

			<Collapsible open={tracksOpen} onOpenChange={setTracksOpen} className="rounded-xl bg-slate-100">
				<CollapsibleTrigger className="flex w-full items-center gap-2 px-4 py-3 text-[13px] font-medium">
					Tracks <Pill className="bg-white">{a.tracks}</Pill>
					{stepSel !== null && <span className="text-xs text-sky-700">{a.steps[stepSel].name.replace(' and ', ' & ')}</span>}
					<ChevronDown className={`ml-auto size-4 transition ${tracksOpen ? 'rotate-180' : ''}`} />
				</CollapsibleTrigger>
				<CollapsibleContent className="px-4 pb-3">
					<ul className="max-h-80 overflow-y-auto">
						{a.files.map(f => {
							const [lt, lc, lh] = LY[f.lyrics] || LY.none
							return (
								<li key={f.file} className={`flex items-center gap-2 border-b border-l-4 border-b-slate-200 py-1.5 pl-1 text-[13px] last:border-b-0 ${p.playing === a.path + '|' + f.file ? 'border-l-yellow-400 bg-yellow-50' : 'border-l-transparent'}`}>
									<button className="shrink-0 rounded-full p-1 hover:bg-white" title="Play" onClick={() => p.play(f)}>
										{p.playing === a.path + '|' + f.file ? <Pause className="size-3" /> : <Play className="size-3" />}
									</button>
									<span className="w-6 shrink-0 tabular-nums text-slate-400">{String(f.track).split('/')[0].padStart(2, '0')}</span>
									<span className="flex-1 truncate" title={f.name}>{f.title}</span>
									<span className="w-10 shrink-0 text-right tabular-nums text-slate-500">{mmss(f.length)}</span>
									<ChannelBadge n={f.channels} />
									{stepSel !== null && (f.checks[stepSel]
										? <span className={`font-semibold ${f.lyrics === 'txt' && a.steps[stepSel].name === 'Lyrics' ? 'text-amber-500' : 'text-emerald-600'}`}>✓</span>
										: <span className="font-semibold text-rose-600">✗</span>)}
									{f.format && <Pill title={f.format.includes('/') ? 'Sample rate in kHz / bit depth' : 'Sample rate in kHz'} className="w-[4.5rem] shrink-0 border border-slate-200 bg-white tabular-nums text-slate-700">{f.format}</Pill>}
									<Pill className={`w-12 shrink-0 ${f.dr ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-500'}`}>{f.dr ? 'DR' + f.dr : 'DR —'}</Pill>
									<Pill title={lh} className={`w-10 shrink-0 ${lc}`}>{lt}</Pill>
									<button className="shrink-0 rounded-full p-1 hover:bg-white" title="Edit lyrics" onClick={() => p.openLyrics(f.file)}><Pencil className="size-3" /></button>
								</li>
							)
						})}
					</ul>
				</CollapsibleContent>
			</Collapsible>

			<Collapsible open={logOpen} onOpenChange={setLogOpen} className="rounded-xl bg-slate-100">
				<CollapsibleTrigger className="flex w-full items-center px-4 py-3 text-[13px] font-medium">
					Log <ChevronDown className={`ml-auto size-4 transition ${logOpen ? 'rotate-180' : ''}`} />
				</CollapsibleTrigger>
				<CollapsibleContent className="px-4 pb-3">
					<div className="max-h-72 overflow-y-auto rounded-lg bg-slate-900 p-3 font-mono text-[11px] text-slate-200">
						{p.log.length ? p.log.slice(-300).map((l, i) => (
							<div key={i} className={l.k === 'ok' ? 'text-emerald-400' : l.k === 'file' ? 'opacity-60' : ''}><span className="mr-3 text-slate-500">{l.t}</span>{l.m}</div>
						)) : <div><span className="mr-3 text-slate-500">—</span>No runs yet</div>}
					</div>
				</CollapsibleContent>
			</Collapsible>

			{big && (
				<div role="dialog" aria-modal="true" aria-label="Full-size cover" title="Click or press Escape to close" onClick={() => setBig(null)} className="fixed inset-0 z-50 grid cursor-zoom-out place-items-center bg-slate-900/80 p-8">
					{/* eslint-disable-next-line @next/next/no-img-element */}
					<img src={big} alt="Full-size cover" className="max-h-full max-w-full object-contain shadow-2xl" />
				</div>
			)}
		</div>
	)
}
