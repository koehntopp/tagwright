'use client'

import { useEffect, useRef, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Album, api, channelLabel, mmss, post } from '@/lib/api'
import { ChannelBadge, CopyBtn } from '@/components/inspector'
import { Shell } from '@/components/dialogs'

type Sort = { key: '' | 'year' | 'tracks'; dir: 1 | -1 }
const val = { year: (r: any) => +r.year || 0, tracks: (r: any) => +(r.n ?? r.tracks) || 0 }

function Results({ rows, sort, setSort, count, pick }: { rows: any[]; sort: Sort; setSort: (s: Sort) => void; count?: (r: any) => React.ReactNode; pick: (id: string) => void }) {
	if (!rows.length) return <p className="text-sm text-slate-500">No releases found.</p>
	const sorted = sort.key ? [...rows].sort((a, b) => { const x = val[sort.key as 'year'](a), y = val[sort.key as 'year'](b); return Number(!x) - Number(!y) || (x - y) * sort.dir }) : rows
	const th = (k: 'year' | 'tracks', l: string, w: string) => (
		<th className={w}><button type="button" className="rounded px-1 py-0.5 text-xs hover:bg-slate-100" onClick={() => setSort({ key: k, dir: sort.key === k ? (-sort.dir as 1 | -1) : 1 })}>{l}{sort.key === k ? (sort.dir > 0 ? ' ▲' : ' ▼') : ''}</button></th>
	)
	return (
		<table className="w-full text-sm">
			<thead className="sticky top-0 z-10 bg-white"><tr className="text-left"><th /><th className="text-xs font-medium">Release</th>{th('year', 'Year', 'w-20')}<th className="w-36 text-xs font-medium">Cat. no.</th>{th('tracks', 'Tracks', 'w-24')}<th /></tr></thead>
			<tbody>
				{sorted.map(r => (
					<tr key={r.id} className="cursor-pointer border-t hover:bg-slate-50" onClick={() => pick(r.id)}>
						<td className="w-12 py-1">{/* eslint-disable-next-line @next/next/no-img-element */}<img src={r.thumb} alt="" className="size-10 rounded bg-slate-100 object-cover" onError={e => e.currentTarget.remove()} /></td>
						<td>
							<div className="font-medium">{r.title}{r.match && <Badge className="ml-1 bg-emerald-100 text-emerald-800 hover:bg-emerald-100" title={r.match === 'MusicBrainz' ? 'Linked from the MusicBrainz release of this album' : 'Same as the Discogs release of this album'}>{r.match} match</Badge>}</div>
							<div className="text-xs text-slate-500">{[r.country, r.format, r.label, r.barcode].filter(Boolean).join(' · ')}</div>
						</td>
						<td className="w-20 tabular-nums">{r.year}</td>
						<td className="w-36 break-words font-mono text-xs">{r.catno}</td>
						<td className="w-24 whitespace-nowrap text-xs text-slate-500">{count ? count(r) : r.tracks ? r.tracks + ' tracks' : ''}</td>
						<td className="text-right"><Button size="xs" variant="outline">Select</Button></td>
					</tr>
				))}
			</tbody>
		</table>
	)
}

// ---- Discogs: search a release, assign album files to its tracks ----
/** Spinner over a dialog's result area while a request runs (a Discogs or MusicBrainz call takes seconds). */
const Busy = ({ text }: { text: string }) => (
	<div role="status" aria-live="polite" className="absolute inset-0 z-10 grid place-items-center">
		<span className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 shadow"><RefreshCw className="size-4 animate-spin" />{text}</span>
	</div>
)

export function DiscogsDialog({ a, onClose, done }: { a: Album | null; onClose: () => void; done: (path: string) => void }) {
	const [q, setQ] = useState(''), [rows, setRows] = useState<any[] | null>(null), [sort, setSort] = useState<Sort>({ key: '', dir: 1 })
	const [rel, setRel] = useState<any>(null), [rid, setRid] = useState(''), [files, setFiles] = useState<any[]>([]), [busy, setBusy] = useState(false), [applying, setApplying] = useState(false), [what, setWhat] = useState(''), [err, setErr] = useState('')
	const token = useRef<object>({})
	useEffect(() => {
		if (!a) return
		setRows(null); setRel(null); setErr(''); setBusy(false); setWhat(''); setQ([a.artist, a.album].filter(Boolean).join(' '))
		if (a.discogs) pick(a.discogs)
	}, [a?.path])  // eslint-disable-line react-hooks/exhaustive-deps
	if (!a) return null
	async function pick(id: string) {
		setBusy(true); setWhat('Loading the release from Discogs…'); setErr('')
		try {
			const d = await post('/api/tracks/propose', { path: a!.path, release_id: id })
			setRid(id); setRel(d.release); setFiles(d.files)
		} catch (e: any) { setErr(e.message) }
		setBusy(false)
	}
	async function search(e: React.FormEvent) {
		e.preventDefault()
		if (!q.trim()) return
		setBusy(true); setWhat('Searching Discogs…'); setErr('')
		try {
			const rs: any[] = await api('/api/discogs/search?q=' + encodeURIComponent(q.trim()) + '&path=' + encodeURIComponent(a!.path))
			setRel(null); setRows(rs); setBusy(false); counts(rs)
		} catch (e: any) { setErr(e.message); setBusy(false) }
	}
	async function counts(rs: any[]) {
		const queue = [...rs], tk = (token.current = {})
		const next = async () => {
			for (let r; (r = queue.shift()) && token.current === tk;) {
				try { r.n = (await api('/api/discogs/tracks?id=' + r.id)).count } catch { r.n = -1 }
				setRows(x => (x ? [...x] : x))
			}
		}
		await Promise.all([next(), next(), next()])
	}
	// default numbering (same rule as the server): 1..n per disc in release order; f.d / f.t hold manual overrides
	const sel = rel ? files.filter(f => f.rel !== null).sort((x, y) => x.rel - y.rel) : []
	const seen: Record<number, number> = {}
	const discs = rel ? [...new Set(sel.map(f => rel.tracks[f.rel].disc as number))].sort((x, y) => x - y) : []
	sel.forEach(f => { const d = rel.tracks[f.rel].disc; seen[d] = (seen[d] || 0) + 1; f.ad = discs.indexOf(d) + 1; f.at = seen[d] })
	const used: Record<number, number> = {}
	files.forEach(f => { if (f.rel !== null) used[f.rel] = (used[f.rel] || 0) + 1 })
	const dup = Object.values(used).some(n => n > 1), n = Object.keys(used).length
	const upd = (k: number, p: any) => setFiles(files.map((f, i) => (i === k ? { ...f, ...p } : f)))
	const apply = async () => {
		setBusy(true); setApplying(true); setWhat('Assigning the tracks…')
		try {
			await post('/api/tracks/apply', { path: a.path, release_id: rid, assignments: files.map(f => ({ file: f.file, rel: f.rel, disc: f.d ?? f.ad, track: f.t ?? f.at })) })
			toast.success('Tracks assigned'); setBusy(false); setApplying(false); onClose(); done(a.path)
		} catch (e: any) { setErr(e.message); setBusy(false); setApplying(false) }
	}
	return (
		<Shell open onClose={onClose} wide="sm:max-w-[64rem]" title="Assign tracks to a release" err={dup ? 'A release track is assigned to more than one file.' : err}
			save={apply} saveLabel={applying ? 'Applying…' : rel ? `Apply (${n} of ${files.length})` : 'Apply'} saveDisabled={!rel || dup || n === 0 || busy} danger={applying}>
			<form className="flex gap-2" onSubmit={search}>
				<Input className="flex-1" value={q} onChange={e => setQ(e.target.value)} placeholder="Artist and album, or a Discogs release ID" />
				<Button size="sm" className="bg-slate-800 text-white hover:bg-slate-700" type="submit" disabled={busy}>{busy && <RefreshCw className="size-3.5 animate-spin" />}Search Discogs</Button>
			</form>
			<AlbumFacts a={a} />
			<div className="relative min-h-48">
			{busy && <Busy text={what} />}
			<div className={`mt-4 max-h-[60vh] overflow-y-auto ${busy ? 'pointer-events-none opacity-50' : ''}`}>
				{rel ? (
					<>
						<div className="mb-3 text-sm"><span className="font-medium">{rel.artist} - {rel.title}</span> <span className="text-slate-500">{rel.year} · {rel.tracks.length} tracks on release · {files.length} files</span></div>
						<table className="w-full text-sm">
							<thead><tr className="text-left text-xs text-slate-500"><th>File</th><th className="w-16">Disc</th><th className="w-16">Track</th><th>Release track</th><th /></tr></thead>
							<tbody>
								{files.map((f, k) => (
									<tr key={f.file} className="border-t">
										<td className="w-1/2 py-1"><div className="flex items-center gap-2"><span className="max-w-xs truncate" title={f.file}>{f.title}</span><ChannelBadge n={f.channels} /></div><div className="text-xs text-slate-500">{f.file} · {mmss(f.duration)}</div></td>
										<td>{f.rel !== null && <Input type="number" min={1} className="h-7 w-14 text-xs" value={f.d ?? f.ad} onChange={e => upd(k, { d: e.target.value === '' ? null : +e.target.value })} />}</td>
										<td>{f.rel !== null && <Input type="number" min={1} className="h-7 w-14 text-xs" value={f.t ?? f.at} onChange={e => upd(k, { t: e.target.value === '' ? null : +e.target.value })} />}</td>
										<td>
											<select className={`h-8 w-full rounded-md border bg-white px-2 text-sm ${f.rel !== null && used[f.rel] > 1 ? 'border-rose-500' : ''}`} value={f.rel ?? ''} onChange={e => upd(k, { rel: e.target.value === '' ? null : +e.target.value, conf: 1, d: null, t: null })}>
												<option value="">Skip (leave as is)</option>
												{rel.tracks.map((t: any) => <option key={t.i} value={t.i}>{t.part_of ? '\u00a0\u00a0\u21b3' : (t.position || t.i + 1)}  {t.title}{t.duration ? ` (${mmss(t.duration)})` : ''}{t.channels ? ` · ${channelLabel(t.channels)}` : ''}</option>)}
											</select>
										</td>
										<td className="w-16 text-right">{f.rel === null ? <Badge variant="secondary">skip</Badge> : f.conf >= 0.6 ? <Badge className="bg-emerald-100 text-emerald-800 hover:bg-emerald-100">match</Badge> : <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-100">check</Badge>}</td>
									</tr>
								))}
							</tbody>
						</table>
						<div className="mt-3 text-xs text-slate-500">Also fills what the tagger used to import and the album lacks: artist, album artist, album title, catalog number and a missing cover. Existing values are kept.</div>
						<div className="mt-1 text-xs text-slate-500">Not in this album: {rel.tracks.filter((t: any) => !used[t.i] && !t.part_of && !rel.tracks.some((p: any) => p.part_of === t.title && used[p.i])).map((t: any) => t.title).join(', ') || 'none'}</div>
					</>
				) : rows && <Results rows={rows} sort={sort} setSort={setSort} pick={pick} count={r => (r.n == null ? '…' : r.n < 0 ? '?' : r.n + ' tracks')} />}
			</div>
			</div>
		</Shell>
	)
}

/** What is known about the album, for searching by hand: each value with a copy icon. */
function AlbumFacts({ a }: { a: Album }) {
	return (
		<div className="mt-1 flex flex-wrap items-center gap-x-3 text-xs text-slate-500">
			{([['Artist', a.artist], ['Album', a.album], ['Year', a.year], ['Catalog #', a.catalog]] as const).filter(([, v]) => v).map(([k, v]) => <span key={k} className="inline-flex items-center">{k}: {v}<CopyBtn text={v} /></span>)}
		</div>
	)
}

// ---- MusicBrainz release search ----
const L = ({ kind, id, text }: { kind: string; id: string; text: string }) => <a className="text-sky-700 underline" href={`https://musicbrainz.org/${kind}/${id}`} target="_blank" rel="noopener">{text}</a>

export function MbDialog({ a, onClose, done }: { a: Album | null; onClose: () => void; done: (path: string) => void }) {
	const [q, setQ] = useState(''), [rows, setRows] = useState<any[] | null>(null), [sort, setSort] = useState<Sort>({ key: '', dir: 1 })
	const [rel, setRel] = useState<any>(null), [busy, setBusy] = useState(false), [applying, setApplying] = useState(false), [what, setWhat] = useState(''), [err, setErr] = useState('')
	useEffect(() => {
		if (!a) return
		setRows(null); setRel(null); setErr(''); setBusy(false); setWhat(''); setQ([a.artist, a.album].filter(Boolean).join(' '))
		if (a.mbid) pick(a.mbid)
	}, [a?.path])  // eslint-disable-line react-hooks/exhaustive-deps
	if (!a) return null
	async function pick(id: string) {
		setBusy(true); setWhat('Loading the release from MusicBrainz…'); setErr('')
		try { setRel(await api(`/api/musicbrainz/release?id=${encodeURIComponent(id)}&path=${encodeURIComponent(a!.path)}`)) } catch (e: any) { setErr(e.message) }
		setBusy(false)
	}
	async function search(e: React.FormEvent) {
		e.preventDefault()
		if (!q.trim()) return
		setBusy(true); setWhat('Searching MusicBrainz…'); setErr('')
		try { setRel(null); setRows(await api(`/api/musicbrainz/search?q=${encodeURIComponent(q.trim())}&path=${encodeURIComponent(a!.path)}`)) } catch (e: any) { setErr(e.message) }
		setBusy(false)
	}
	const apply = async () => {
		setBusy(true); setApplying(true); setWhat('Writing the MusicBrainz tags…')
		try { await post('/api/musicbrainz/apply', { path: a.path, id: rel.id }); toast.success('MusicBrainz release applied'); setBusy(false); setApplying(false); onClose(); done(a.path) }
		catch (e: any) { setErr(e.message); setBusy(false); setApplying(false) }
	}
	const commas = (xs: any[]) => xs.map((x, i) => <span key={x.id}>{i ? ', ' : ''}<L kind="artist" id={x.id} text={x.name} /></span>)
	return (
		<Shell open onClose={onClose} wide="sm:max-w-[64rem]" title="Choose a MusicBrainz release" err={err} save={apply} saveLabel={applying ? 'Applying…' : 'Save'} saveDisabled={!rel || busy} danger={applying}>
			<form className="flex gap-2" onSubmit={search}>
				<Input className="flex-1" value={q} onChange={e => setQ(e.target.value)} placeholder="Artist and album, or a MusicBrainz release ID" />
				<Button size="sm" className="bg-slate-800 text-white hover:bg-slate-700" type="submit" disabled={busy}>{busy && <RefreshCw className="size-3.5 animate-spin" />}Search MusicBrainz</Button>
			</form>
			<AlbumFacts a={a} />
			<div className="relative min-h-48">
			{busy && <Busy text={what} />}
			<div className={`mt-4 max-h-[60vh] overflow-y-auto ${busy ? 'pointer-events-none opacity-50' : ''}`}>
				{rel ? (
					<>
						<div className="mb-3 text-sm"><span className="font-medium">{rel.artist} - {rel.name}</span> <span className="text-slate-500">{[rel.year, rel.country, rel.format, rel.label, rel.catno].filter(Boolean).join(' · ')} · {rel.tracks.length} tracks on release · {rel.files} files</span></div>
						<table className="mb-3 w-full text-sm"><tbody>
							<tr className="border-b"><td className="w-40 py-1 text-slate-500">Release</td><td className="font-mono text-xs"><L kind="release" id={rel.id} text={rel.id} /></td></tr>
							<tr className="border-b"><td className="py-1 text-slate-500">Release group (master)</td><td>{rel.group.id ? <><L kind="release-group" id={rel.group.id} text={rel.group.title || rel.group.id} /> <span className="text-xs text-slate-500">{[rel.group.type, rel.group.first].filter(Boolean).join(' · ')}</span></> : <span className="text-slate-500">none</span>}</td></tr>
							<tr><td className="py-1 text-slate-500">Album artist</td><td>{rel.artists.length ? commas(rel.artists) : <span className="text-slate-500">none</span>}</td></tr>
						</tbody></table>
						<table className="w-full text-sm">
							<thead><tr className="text-left text-xs text-slate-500"><th className="w-16">Disc</th><th className="w-16">Track</th><th>Title</th><th>Artist</th><th className="w-16 text-right">Length</th><th className="w-16 pl-2">Channels</th></tr></thead>
							<tbody>{rel.tracks.map((t: any, i: number) => <tr key={i} className="border-t"><td>{t.disc}</td><td>{t.position}</td><td>{t.title}</td><td className="text-slate-700">{commas(t.artists)}</td><td className="text-right text-slate-500">{mmss(t.duration)}</td><td className="pl-2"><ChannelBadge n={t.channels} hint /></td></tr>)}</tbody>
						</table>
						<div className="mt-3 text-xs text-slate-500">Apply writes the release ID, the release group and album artist IDs and links to every file, and the artist ID and link to each file whose title matches a release track. Barcode, ASIN, release country, status, type and disambiguation are filled only where the file has none yet. Titles, track numbers and everything else stay as they are.</div>
					</>
				) : rows && <Results rows={rows} sort={sort} setSort={setSort} pick={pick} />}
			</div>
			</div>
		</Shell>
	)
}
