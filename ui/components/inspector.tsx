'use client'

import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown, Copy, Pause, Pencil, Play, TriangleAlert, Upload, XCircle } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert } from '@/components/ui/alert'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Album, Job, LogLine, TrackFile, api, coverUrl, fmtBytes, mmss, title } from '@/lib/api'

export function copy(text: string) {
	navigator.clipboard.writeText(text).then(() => toast.success('Copied'), () => toast.error('Copy failed'))
}
export const CopyBtn = ({ text }: { text: string }) => (
	<button
		onClick={e => { e.stopPropagation(); copy(text) }}
		title="Copy"
		className="shrink-0 rounded-full p-1 text-slate-400 hover:bg-black/5 hover:text-slate-700"
	>
		<Copy className="size-3" />
	</button>
)

const LY = {
	lrc: ['LRC', 'bg-emerald-500 text-white'],
	txt: ['TXT', 'bg-amber-400 text-amber-950'],
	instr: ['Instrumental', 'bg-sky-100 text-sky-800'],
	none: ['No lyrics', 'bg-rose-100 text-rose-700'],
} as const

const Pill = ({ className = '', ...p }: React.ComponentProps<'span'>) => (
	<span {...p} className={`inline-flex h-5 items-center justify-center rounded-full px-2 text-[11px] font-medium ${className}`} />
)

export const IdBadge = ({ l, v, full }: { l: 'D' | 'MB'; v: string; full?: boolean }) => {
	const icon = l === 'D' ? '/static/discogs.png' : '/static/musicbrainz.ico'
	const url = (l === 'D' ? 'https://www.discogs.com/release/' : 'https://musicbrainz.org/release/') + encodeURIComponent(v)
	return v ? (
		<a href={url} target="_blank" rel="noopener" onClick={e => e.stopPropagation()} className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 font-mono text-[11px] hover:bg-slate-200">
			{/* eslint-disable-next-line @next/next/no-img-element */}
			<img src={icon} alt={l} className="size-3.5 rounded-sm" />
			{!full && v.length > 13 ? v.slice(0, 8) : v}
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
	run: () => void
	move: () => void
	inLibrary?: boolean
	openEditor: (tab: string) => void
	openAlbum: () => void
	openDiscogs: () => void
	openMb: () => void
	openLyrics: (file: string) => void
	playing: string | null
	play: (f: TrackFile) => void
	delCover: () => void
	putCover: (f: File) => void
}

export function Inspector(p: Props) {
	const { a, job } = p
	const [stepSel, setStep] = useState<number | null>(null)
	const [tracksOpen, setTracksOpen] = useState(true)
	const [logOpen, setLogOpen] = useState(false)
	const [drag, setDrag] = useState(false)
	const fileRef = useRef<HTMLInputElement>(null)
	// non-consequential notes where MusicBrainz and Discogs disagree (selected album only: one cached MusicBrainz lookup)
	const [mbNotes, setMbNotes] = useState<string[]>([])
	useEffect(() => {
		setMbNotes([])
		if (!a.discogs || !a.mbid) return
		let live = true
		api<{ notes: string[] }>('/api/musicbrainz/check?path=' + encodeURIComponent(a.path)).then(r => live && setMbNotes(r.notes), () => {})
		return () => { live = false }
	}, [a.path, a.discogs, a.mbid, a.mtime])
	const running = job.state === 'running' && job.path === a.path

	const cov = a.cover
	return (
		<div className="space-y-5 p-6">
			<div className="flex gap-4">
				<div className="w-24 shrink-0">
					<div
						className={`rounded-xl transition-shadow ${drag ? 'ring-4 ring-slate-800' : ''}`}
						title="Drop an image here to replace the cover"
						onDragOver={e => { e.preventDefault(); setDrag(true) }}
						onDragLeave={() => setDrag(false)}
						onDrop={e => {
							e.preventDefault(); setDrag(false)
							const f = [...e.dataTransfer.files].find(f => f.type.startsWith('image/'))
							f ? p.putCover(f) : toast.error('Drop an image file')
						}}
					>
						<CoverImg a={a} className="size-24 rounded-xl shadow" />
					</div>
					<div className="mt-1.5 flex items-center justify-center gap-2.5">
						<button title="Upload a different cover" onClick={() => fileRef.current?.click()}><Upload className="size-[18px]" /></button>
						<a href={`https://covers.musichoarders.xyz/?${new URLSearchParams({ artist: a.artist || '', album: title(a) })}`} target="_blank" rel="noopener" title="Search covers on covers.musichoarders.xyz">
							{/* eslint-disable-next-line @next/next/no-img-element */}
							<img src="/static/musichoarders.svg" alt="COV" className="size-3.5 rounded-sm bg-slate-800 p-px" />
						</a>
						<a href={`https://albumartexchange.com/covers?${new URLSearchParams({ q: [a.artist, title(a)].filter(Boolean).join(' '), fltr: 'ALL', sort: 'SCORE', status: '', size: 'any' })}`} target="_blank" rel="noopener" title="Search covers on albumartexchange.com">
							{/* eslint-disable-next-line @next/next/no-img-element */}
							<img src="/static/albumartexchange.ico" alt="AAE" className="size-3.5 rounded-sm" />
						</a>
						{cov && <button className="text-rose-600" title="Remove the cover" onClick={p.delCover}><XCircle className="size-[18px]" /></button>}
					</div>
					<div className="mt-1 text-center text-sm tabular-nums text-slate-500" title={cov ? `${cov.embedded ? 'Embedded cover' : 'Folder image, not embedded'}, ${fmtBytes(cov.bytes)}` : ''}>
						{cov ? `${cov.w}×${cov.h}` : 'no cover'}
					</div>
					<input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={e => e.target.files?.[0] && p.putCover(e.target.files[0])} />
				</div>
				<div className="min-w-0">
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
					<div className="mt-0.5 text-xs text-slate-500">{[a.edition, a.year].filter(Boolean).join(' · ')}</div>
					<div className="mt-2 flex flex-wrap items-center gap-1">
						<IdBadge l="D" v={a.discogs} />
						<button onClick={p.openDiscogs} title="Change the Discogs release" className="mr-1"><Pencil className="size-3" /></button>
						<IdBadge l="MB" v={a.mbid} />
						<button onClick={p.openMb} title="Choose the MusicBrainz release" className="mr-1"><Pencil className="size-3" /></button>
						{a.dr && <Pill className="bg-emerald-100 text-emerald-800" title="Album dynamic range">DR{a.dr}</Pill>}
					</div>
				</div>
			</div>

			<div className="flex gap-2">
				<Button className="flex-1 bg-slate-800 text-white hover:bg-slate-700" onClick={() => p.openEditor('album')}>Tag Editor</Button>
				<Button className="flex-1" variant="outline" disabled={a.status === 'needs' || job.state === 'running'} onClick={p.run}>Run fixes</Button>
				<Button className="flex-1" variant="outline" disabled={p.inLibrary || a.status !== 'fixed' || a.issues.some(i => i.level === 'ingest') || job.state === 'running'} title={p.inLibrary ? 'This album is already in the library' : undefined} onClick={p.move}>Move to library</Button>
			</div>

			<div className="space-y-2">
				{a.issues.map(i => (
					<Alert key={i.text} className={`flex items-center gap-2 text-[13px] ${i.level === 'info' ? 'border-sky-200 bg-sky-50 text-sky-900' : i.level === 'error' ? 'border-rose-300 bg-rose-50 text-rose-900' : 'border-amber-200 bg-amber-50 text-amber-900'}`}>
						<TriangleAlert className="size-4 shrink-0" />
						<span className="flex-1">{i.text}</span>
						{i.action && (
							<Button size="xs" variant="outline" onClick={() => ({ search: p.openDiscogs, album: () => p.openEditor('album'), tracks: () => p.openEditor('tracks'), cover: () => fileRef.current?.click() } as Record<string, () => void>)[i.action!]()}>
								{{ search: 'Search', album: 'Tag Editor', tracks: 'Tag Editor', cover: 'Upload' }[i.action]}
							</Button>
						)}
					</Alert>
				))}
			</div>

			{mbNotes.length > 0 && (
				<div className="space-y-2">
					{mbNotes.map(n => (
						<Alert key={n} className="flex items-center gap-2 border-sky-200 bg-sky-50 text-[13px] text-sky-900">
							<TriangleAlert className="size-4 shrink-0" />
							<span className="flex-1">{n}</span>
							<Button size="xs" variant="outline" onClick={p.openMb}>MusicBrainz</Button>
						</Alert>
					))}
				</div>
			)}

			<div className="border-b border-slate-200 py-2 text-[13px]">
				<div className="mb-1 text-slate-500">New folder</div>
				{a.new_title ? <code className="break-all text-xs">{a.new_title}</code> : <span className="text-xs text-slate-400">Not ready: artist or album is empty</span>}
			</div>

			<div>
				<h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-500">Pipeline</h4>
				<ol className="grid grid-cols-6 gap-1 text-center text-[11px] leading-tight">
					{a.steps.map((s, i) => (
						<li key={s.name} title={s.note} className="cursor-pointer" onClick={() => { setStep(stepSel === i ? null : i); setTracksOpen(true) }}>
							<div className={`mx-auto mb-1 grid size-7 place-items-center rounded-full text-white ${s.done ? (s.partial ? 'bg-amber-400' : 'bg-emerald-500') : 'bg-slate-200 text-slate-500'} ${running && s.name === job.step ? 'animate-pulse ring-2 ring-sky-400' : ''}`}>
								{s.done ? <Check className="size-4" /> : i + 1}
							</div>
							<span className={`rounded px-1 ${stepSel === i ? 'bg-slate-800/10 font-medium' : ''}`}>{s.name.replace(' and ', ' & ')}</span>
						</li>
					))}
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
							const [lt, lc] = LY[f.lyrics] || LY.none
							return (
								<li key={f.file} className={`flex items-center gap-2 border-b border-l-4 border-b-slate-200 py-1.5 pl-1 text-[13px] last:border-b-0 ${p.playing === a.path + '|' + f.file ? 'border-l-yellow-400 bg-yellow-50' : 'border-l-transparent'}`}>
									<button className="shrink-0 rounded-full p-1 hover:bg-white" title="Play" onClick={() => p.play(f)}>
										{p.playing === a.path + '|' + f.file ? <Pause className="size-3" /> : <Play className="size-3" />}
									</button>
									<span className="w-6 shrink-0 tabular-nums text-slate-400">{String(f.track).split('/')[0].padStart(2, '0')}</span>
									<span className="flex-1 truncate" title={f.name}>{f.title}</span>
									<span className="w-10 shrink-0 text-right tabular-nums text-slate-500">{mmss(f.length)}</span>
									{stepSel !== null && (f.checks[stepSel]
										? <span className={`font-semibold ${f.lyrics === 'txt' && a.steps[stepSel].name === 'Lyrics' ? 'text-amber-500' : 'text-emerald-600'}`}>✓</span>
										: <span className="font-semibold text-rose-600">✗</span>)}
									<Pill className={`w-12 shrink-0 ${f.dr ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-500'}`}>{f.dr ? 'DR' + f.dr : 'DR —'}</Pill>
									<Pill className={`w-24 shrink-0 ${lc}`}>{lt}</Pill>
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
		</div>
	)
}
