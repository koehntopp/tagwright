'use client'

import { Fragment, useEffect, useRef, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Album, api, channelLabel, mmss, post } from '@/lib/api'
import { ChannelBadge, CopyBtn } from '@/components/inspector'
import { Shell } from '@/components/dialogs'
import { DividerGap, SubtitleDivider } from '@/components/subtitle-divider'

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

/** A typed Disc or Track field: digits, kept as typed; empty (or unset) means the default number. */
const num = (v: string | number | null | undefined): number | undefined => (v === null || v === undefined || v === '' ? undefined : Number(v))

/** The title a release track gives a file: a part of a medley as "Medley (Part)" (ADR 0110; server: import_title). */
const importTitle = (t: any): string => (t.part_of ? `${t.part_of} (${t.title})` : t.title)

/** The release's tracks in runs of the same disc and subtitle, each with a "Disc N · subtitle" label for the dropdown
 *  (ADR 0108); a release with one disc and no subtitles is one run without a label. */
function trackGroups(rel: any): { key: string; label: string; tracks: any[] }[] {
	const out: { key: string; label: string; tracks: any[] }[] = []
	for (const t of rel.tracks) {
		const run = `${t.disc}\u0000${t.subtitle || ''}`
		if (out.at(-1)?.key.split('\u0001')[1] !== run) out.push({ key: `${out.length}\u0001${run}`, label: [`Disc ${t.disc}`, t.subtitle].filter(Boolean).join(' · '), tracks: [] })
		out.at(-1)!.tracks.push(t)
	}
	const plain = new Set(rel.tracks.map((t: any) => t.disc)).size < 2 && !rel.tracks.some((t: any) => t.subtitle)
	return plain ? [{ key: 'all', label: '', tracks: rel.tracks }] : out
}

/** Default numbering (same rule as the server): 1..n per disc in release order; f.d / f.t hold manual overrides.
 *  A release track may go to one file per disc of the album (f.disc, the file's own disc); when one does, or the
 *  album has more discs than the release discs its tracks are on, every disc of the album is numbered on its own
 *  (ADR 0102, 0109). Sets f.ad / f.at on the files and returns how often each
 *  release track is used, the release tracks used twice on one disc of the album, and the number of assigned files. */
function numbering(rel: any, files: any[]) {
	const sel = rel ? files.filter(f => f.rel !== null).sort((x, y) => x.rel - y.rel) : []
	const used: Record<number, number> = {}, onDisc: Record<string, number> = {}
	sel.forEach(f => { used[f.rel] = (used[f.rel] || 0) + 1; const k = `${f.rel}:${f.disc}`; onDisc[k] = (onDisc[k] || 0) + 1 })
	// every disc of the album on its own: a release track on several of them (ADR 0102), or more album discs than
	// release discs, as when Discogs lists the mixes of a Blu-ray as one disc (ADR 0109); the server's per_album_disc
	const split = Object.values(used).some(n => n > 1) || new Set(sel.map(f => f.disc)).size > new Set(sel.map(f => rel.tracks[f.rel].disc)).size
	const group = (f: any) => `${split ? f.disc : 0}:${rel.tracks[f.rel].disc}`
	const order = (g: string) => g.split(':').map(Number)
	const discs = [...new Set(sel.map(group))].sort((x, y) => order(x)[0] - order(y)[0] || order(x)[1] - order(y)[1])
	const seen: Record<string, number> = {}
	sel.forEach(f => { const g = group(f); seen[g] = (seen[g] || 0) + 1; f.ad = discs.indexOf(g) + 1; f.at = seen[g] })
	const twice = new Set(sel.filter(f => onDisc[`${f.rel}:${f.disc}`] > 1).map(f => f.file as string))
	return { used, twice, dup: twice.size > 0, n: sel.length }
}

/** Runs of the subtitle dividers (ADR 0081): neighbouring assigned files whose release tracks share a disc and a
 *  subtitle. `ovr` holds the owner's changes per run start: `text` (typed subtitle), `keep` (Keep mine), `split` (a divider
 *  added by hand) and `merge` (a divider of the release removed). Skipped files stay with the run above. */
type Ovr = { text?: string; keep?: boolean; split?: boolean; merge?: boolean }
type Run = { start: number; key: string; disc: number; relSub: string; inside: boolean; idx: number[]; text: string; keep: boolean; was: string; differs: boolean }
function subtitleRuns(rel: any, files: any[], ovr: Record<string, Ovr>) {
	const runs: Run[] = []
	let cur: Run | null = null, lastSub = ''
	if (rel) files.forEach((f, i) => {
		if (f.rel === null) return
		const t = rel.tracks[f.rel], relSub: string = t.subtitle || '', o = ovr[f.file], disc: number = num(f.d) ?? f.ad ?? t.disc
		const discStart = !cur || disc !== cur.disc
		if (!cur || discStart || ((relSub !== lastSub || o?.split) && !o?.merge)) {
			cur = { start: i, key: f.file, disc, relSub, inside: !discStart, idx: [], text: '', keep: false, was: '', differs: false }
			runs.push(cur)
		}
		cur.idx.push(i); lastSub = relSub
	})
	const subOf: Record<string, string | null> = {}
	for (const r of runs) {
		const o = ovr[r.key], was = [...new Set(r.idx.map(i => files[i].subtitle as string).filter(Boolean))]
		r.text = o?.text ?? r.relSub
		r.differs = was.some(x => x !== r.relSub)
		r.keep = o?.keep ?? r.differs
		r.was = was.join(' · ')
		for (const i of r.idx) subOf[files[i].file] = r.keep ? null : r.text.trim() || null
	}
	return { runs, subOf, multi: new Set(runs.map(r => r.disc)).size > 1 }
}

/** The file -> release track table of both dialogs (ADR 0013, 0078, 0081). */
function AssignTable({ rel, files, twice, upd, numbers, ovr, setOvr }: { rel: any; files: any[]; twice: Set<string>; upd: (k: number, p: any) => void; numbers: boolean; ovr: Record<string, Ovr>; setOvr: (o: Record<string, Ovr>) => void }) {
	const { runs, multi } = subtitleRuns(rel, files, ovr)
	const [editing, setEditing] = useState<string | null>(null)
	const runAt = (k: number) => runs.find(r => r.start === k)
	const setO = (key: string, o: Ovr | null) => { const n = { ...ovr }; o ? (n[key] = o) : delete n[key]; setOvr(n) }
	const lastAssigned = (k: number) => files.slice(0, k).some(f => f.rel !== null)
	return (
		<table className="w-full table-fixed text-sm">
			<thead><tr className="text-left text-xs text-slate-500"><th>File and title</th><th className="w-16">Disc</th><th className="w-16">Track</th><th className="w-72">Release track</th><th className="w-20" /></tr></thead>
			<tbody>
				{files.map((f, k) => {
					const run = runAt(k), o = run ? ovr[run.key] : undefined
					const bar = run && (run.inside || multi || run.relSub || o?.text)
					return (
					<Fragment key={f.file}>
					{bar && run && (
						<SubtitleDivider cols={5} disc={!run.inside && multi ? String(run.disc) : undefined} inside={run.inside} subtitle={run.text} count={run.idx.length} was={run.was} differs={run.differs} keep={run.keep} disabled={!numbers}
							onKeep={keep => setO(run.key, { ...o, keep })}
							editing={editing === run.key} onEdit={() => setEditing(run.key)}
							onSet={t => { setEditing(null); if (!t.trim() && o?.split && !o.text) setO(run.key, null); else setO(run.key, { ...o, text: t.trim(), keep: false }) }}
							onCancel={() => { setEditing(null); if (o?.split && !o.text) setO(run.key, null) }}
							onRemove={run.inside ? () => (o?.split ? setO(run.key, null) : setO(run.key, { ...o, merge: true })) : undefined} />
					)}
					{numbers && f.rel !== null && !run && lastAssigned(k) && <DividerGap cols={5} onAdd={() => { setO(f.file, { split: true, text: '' }); setEditing(f.file) }} />}
					<tr className="border-t">
						<td className="py-1 pr-3">
							<div className="mb-0.5 truncate text-xs text-slate-400" title={f.file}>File: {f.file} · {mmss(f.duration)}</div>
							{numbers && f.rel !== null ? (
								<>
									<div className="flex items-center gap-2">
										<Input className="h-7 border-sky-300 bg-sky-50 text-sm" aria-label="New title" title="New title from the release; editable" value={f.nt ?? importTitle(rel.tracks[f.rel])} onChange={e => upd(k, { nt: e.target.value })} />
										<ChannelBadge n={f.channels} />
									</div>
									<div className="mt-0.5 flex items-center text-xs text-slate-400"><span className="truncate">Was: {f.title}</span><CopyBtn text={f.title} title="Copy the old title" /></div>
								</>
							) : (
								<div className="flex items-center gap-2"><span className="max-w-xs truncate text-slate-400" title={f.file}>{f.title}</span><ChannelBadge n={f.channels} /></div>
							)}
						</td>
						<td>{f.rel !== null && <Input type="text" inputMode="numeric" pattern="[0-9]*" disabled={!numbers} aria-label="Disc" className={`h-7 w-14 text-xs ${numbers ? '' : 'bg-slate-50 text-slate-400'}`} value={f.d ?? f.ad} onFocus={e => e.target.select()} onChange={e => upd(k, { d: e.target.value.replace(/\D/g, '') })} />}</td>
						<td>{f.rel !== null && <Input type="text" inputMode="numeric" pattern="[0-9]*" disabled={!numbers} aria-label="Track" className={`h-7 w-14 text-xs ${numbers ? '' : 'bg-slate-50 text-slate-400'}`} value={f.t ?? f.at} onFocus={e => e.target.select()} onChange={e => upd(k, { t: e.target.value.replace(/\D/g, '') })} />}</td>
						<td>
							<select className={`h-8 w-full rounded-md border bg-white px-2 text-sm ${twice.has(f.file) ? 'border-rose-500' : ''}`} value={f.rel ?? ''} onChange={e => upd(k, { rel: e.target.value === '' ? null : +e.target.value, conf: 1, d: null, t: null, nt: undefined })}>
								<option value="">Skip (leave as is)</option>
								{trackGroups(rel).map(g => {
									const opts = g.tracks.map((t: any) => <option key={t.i} value={t.i}>{t.part_of ? '\u00a0\u00a0\u21b3' : (t.position || t.i + 1)}  {t.title}{t.duration ? ` (${mmss(t.duration)})` : ''}{t.channels ? ` · ${channelLabel(t.channels)}` : ''}</option>)
									return g.label ? <optgroup key={g.key} label={g.label}>{opts}</optgroup> : opts
								})}
							</select>
						</td>
						<td className="pl-2 pr-3 text-right">{f.rel === null ? <Badge variant="secondary">skip</Badge> : f.conf >= 0.6 ? <Badge className="bg-emerald-100 text-emerald-800 hover:bg-emerald-100">match</Badge> : <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-100">check</Badge>}</td>
					</tr>
					</Fragment>
					)
				})}
			</tbody>
		</table>
	)
}

/** "Import song titles": whether the release's titles and numbering replace the files'; remembered from the last apply.
 *  The checkbox sits in the release line (top right), the explanation below the table. */
function TitlesCheck({ on, set }: { on: boolean; set: (v: boolean) => void }) {
	return <label className="flex shrink-0 items-center gap-2 text-sm"><input type="checkbox" className="size-4" checked={on} onChange={e => set(e.target.checked)} />Import song titles</label>
}
function TitlesHint({ on }: { on: boolean }) {
	return (
		<div className="mt-3 text-sm">
			<p className="text-xs text-slate-500">Off: only the album data is imported (release IDs, CATALOGNUMBER, year and country); the files keep their TITLE, ARTIST, TRACKNUMBER, DISCNUMBER and DISCSUBTITLE.<br />On: the files also get the release's TITLE, ARTIST, TRACKNUMBER, DISCNUMBER and DISCSUBTITLE.</p>
			{on && <p className="mt-1 text-xs text-slate-500">Blue fields: data from the release that will be written (editable). Grey text: what the file has now. “Keep mine” writes no subtitle for that part.</p>}
		</div>
	)
}

export function DiscogsDialog({ a, onClose, done }: { a: Album | null; onClose: () => void; done: (path: string) => void }) {
	const [q, setQ] = useState(''), [rows, setRows] = useState<any[] | null>(null), [sort, setSort] = useState<Sort>({ key: '', dir: 1 })
	const [rel, setRel] = useState<any>(null), [rid, setRid] = useState(''), [files, setFiles] = useState<any[]>([]), [busy, setBusy] = useState(false), [applying, setApplying] = useState(false), [what, setWhat] = useState(''), [err, setErr] = useState(''), [titles, setTitles] = useState(true), [ovr, setOvr] = useState<Record<string, Ovr>>({})
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
			setRid(id); setRel(d.release); setFiles(d.files); setTitles(d.import_titles); setOvr({})
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
	const { used, twice, dup, n } = numbering(rel, files)
	const sr = subtitleRuns(rel, files, ovr)
	const upd = (k: number, p: any) => setFiles(files.map((f, i) => (i === k ? { ...f, ...p } : f)))
	const apply = async () => {
		setBusy(true); setApplying(true); setWhat('Assigning the tracks…')
		try {
			await post('/api/tracks/apply', { path: a.path, release_id: rid, import_titles: titles, assignments: files.map(f => ({ file: f.file, rel: f.rel, disc: num(f.d) ?? f.ad, track: num(f.t) ?? f.at, title: f.nt, subtitle: sr.subOf[f.file] ?? null })) })
			toast.success('Tracks assigned'); setBusy(false); setApplying(false); onClose(); done(a.path)
		} catch (e: any) { setErr(e.message); setBusy(false); setApplying(false) }
	}
	return (
		<Shell open onClose={onClose} wide="sm:max-w-[64rem]" title="Assign tracks to a release" err={dup ? 'A release track is assigned to more than one file of the same disc.' : err}
			save={apply} saveLabel={applying ? 'Applying…' : rel ? `Apply (${n} of ${files.length})` : 'Apply'} saveDisabled={!rel || dup || n === 0 || busy} danger={applying}>
			<form className="flex gap-2" onSubmit={search}>
				<Input className="flex-1" value={q} onChange={e => setQ(e.target.value)} placeholder="Artist and album, or a Discogs release ID" />
				<Button size="sm" className="bg-slate-800 text-white hover:bg-slate-700" type="submit" disabled={busy}>{busy && <RefreshCw className="size-3.5 animate-spin" />}Search Discogs</Button>
			</form>
			<AlbumFacts a={a} id="Discogs ID" />
			<div className="relative min-h-48">
			{busy && <Busy text={what} />}
			<div className={`mt-4 max-h-[60vh] overflow-y-auto ${busy ? 'pointer-events-none opacity-50' : ''}`}>
				{rel ? (
					<>
						<div className="mb-3 flex items-center gap-3 text-sm"><div className="min-w-0 flex-1"><span className="font-medium">{rel.artist} - {rel.title}</span> <span className="text-slate-500">{rel.year} · {rel.tracks.length} tracks on release · {files.length} files</span></div><TitlesCheck on={titles} set={setTitles} /></div>
						<AssignTable rel={rel} files={files} twice={twice} upd={upd} numbers={titles} ovr={ovr} setOvr={setOvr} />
						<TitlesHint on={titles} />
						<div className="mt-3 text-xs text-slate-500">Always written from Discogs: DISCOGS_RELEASE_ID, ALBUMARTIST, ALBUM, CATALOGNUMBER, ALBUM_FORMAT (each unless its _OVERRIDE tag is set), COMPOSER, PRODUCER, ENGINEER, the other credit tags and the DISCOGS_* tags.<br />Written only where a file has none: a cover, and ARTIST while “Import song titles” is off.</div>
						<div className="mt-1 text-xs text-slate-500">Not in this album: {rel.tracks.filter((t: any) => !used[t.i] && !t.part_of && !rel.tracks.some((p: any) => p.part_of === t.title && used[p.i])).map((t: any) => t.title).join(', ') || 'none'}</div>
					</>
				) : rows && <Results rows={rows} sort={sort} setSort={setSort} pick={pick} count={r => (r.n == null ? '…' : r.n < 0 ? '?' : r.n + ' tracks')} />}
			</div>
			</div>
		</Shell>
	)
}

/** What is known about the album, for searching by hand: each value with a copy icon. */
/** The album's facts for searching by hand, and the release ID it has now (`id`: 'Discogs ID' or 'MusicBrainz ID'). */
function AlbumFacts({ a, id }: { a: Album; id: 'Discogs ID' | 'MusicBrainz ID' }) {
	const current = id === 'Discogs ID' ? a.discogs : a.mbid
	return (
		<div className="mt-1 flex flex-wrap items-center gap-x-3 text-xs text-slate-500">
			{([['Artist', a.artist], ['Album', a.album], ['Year', a.year], ['Catalog #', a.catalog], [id, current]] as const).filter(([, v]) => v).map(([k, v]) => <span key={k} className="inline-flex items-center">{k}: {v}<CopyBtn text={v} /></span>)}
		</div>
	)
}

// ---- MusicBrainz release search ----
const L = ({ kind, id, text }: { kind: string; id: string; text: string }) => <a className="text-sky-700 underline" href={`https://musicbrainz.org/${kind}/${id}`} target="_blank" rel="noopener">{text}</a>

export function MbDialog({ a, onClose, done }: { a: Album | null; onClose: () => void; done: (path: string) => void }) {
	const [q, setQ] = useState(''), [rows, setRows] = useState<any[] | null>(null), [sort, setSort] = useState<Sort>({ key: '', dir: 1 })
	const [rel, setRel] = useState<any>(null), [busy, setBusy] = useState(false), [applying, setApplying] = useState(false), [what, setWhat] = useState(''), [err, setErr] = useState(''), [files, setFiles] = useState<any[]>([]), [titles, setTitles] = useState(false), [ovr, setOvr] = useState<Record<string, Ovr>>({})
	useEffect(() => {
		if (!a) return
		setRows(null); setRel(null); setErr(''); setBusy(false); setWhat(''); setQ([a.artist, a.album].filter(Boolean).join(' '))
		if (a.mbid) pick(a.mbid)
	}, [a?.path])  // eslint-disable-line react-hooks/exhaustive-deps
	if (!a) return null
	async function pick(id: string) {
		setBusy(true); setWhat('Loading the release from MusicBrainz…'); setErr('')
		try {
			const d = await post('/api/tracks/propose', { path: a!.path, release_id: id, source: 'musicbrainz' })
			setRel(d.release); setFiles(d.files); setTitles(d.import_titles); setOvr({})
		} catch (e: any) { setErr(e.message) }
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
		try { await post('/api/musicbrainz/apply', { path: a.path, id: rel.id, import_titles: titles, assignments: files.map(f => ({ file: f.file, rel: f.rel, disc: num(f.d) ?? f.ad, track: num(f.t) ?? f.at, title: f.nt, subtitle: sr.subOf[f.file] ?? null })) }); toast.success('MusicBrainz release applied'); setBusy(false); setApplying(false); onClose(); done(a.path) }
		catch (e: any) { setErr(e.message); setBusy(false); setApplying(false) }
	}
	const { used, twice, dup, n } = numbering(rel, files)
	const sr = subtitleRuns(rel, files, ovr)
	const upd = (k: number, p: any) => setFiles(files.map((f, i) => (i === k ? { ...f, ...p } : f)))
	const commas = (xs: any[]) => xs.map((x, i) => <span key={x.id}>{i ? ', ' : ''}<L kind="artist" id={x.id} text={x.name} /></span>)
	return (
		<Shell open onClose={onClose} wide="sm:max-w-[64rem]" title="Choose a MusicBrainz release" err={dup ? 'A release track is assigned to more than one file of the same disc.' : err} save={apply} saveLabel={applying ? 'Applying…' : rel ? `Apply (${n} of ${files.length})` : 'Apply'} saveDisabled={!rel || dup || busy} danger={applying}>
			<form className="flex gap-2" onSubmit={search}>
				<Input className="flex-1" value={q} onChange={e => setQ(e.target.value)} placeholder="Artist and album, or a MusicBrainz release ID" />
				<Button size="sm" className="bg-slate-800 text-white hover:bg-slate-700" type="submit" disabled={busy}>{busy && <RefreshCw className="size-3.5 animate-spin" />}Search MusicBrainz</Button>
			</form>
			<AlbumFacts a={a} id="MusicBrainz ID" />
			<div className="relative min-h-48">
			{busy && <Busy text={what} />}
			<div className={`mt-4 max-h-[60vh] overflow-y-auto ${busy ? 'pointer-events-none opacity-50' : ''}`}>
				{rel ? (
					<>
						<div className="mb-3 flex items-center gap-3 text-sm"><div className="min-w-0 flex-1"><span className="font-medium">{rel.artist} - {rel.name}</span> <span className="text-slate-500">{[rel.year, rel.country, rel.format, rel.label, rel.catno].filter(Boolean).join(' · ')} · {rel.tracks.length} tracks on release · {files.length} files</span></div><TitlesCheck on={titles} set={setTitles} /></div>
						<table className="mb-3 w-full text-sm"><tbody>
							<tr className="border-b"><td className="w-40 py-1 text-slate-500">Release</td><td className="font-mono text-xs"><L kind="release" id={rel.id} text={rel.id} /></td></tr>
							<tr className="border-b"><td className="py-1 text-slate-500">Release group (master)</td><td>{rel.group.id ? <><L kind="release-group" id={rel.group.id} text={rel.group.title || rel.group.id} /> <span className="text-xs text-slate-500">{[rel.group.type, rel.group.first].filter(Boolean).join(' · ')}</span></> : <span className="text-slate-500">none</span>}</td></tr>
							<tr><td className="py-1 text-slate-500">Album artist</td><td>{rel.artists.length ? commas(rel.artists) : <span className="text-slate-500">none</span>}</td></tr>
						</tbody></table>
						<AssignTable rel={rel} files={files} twice={twice} upd={upd} numbers={titles} ovr={ovr} setOvr={setOvr} />
						<TitlesHint on={titles} />
						<div className="mt-3 text-xs text-slate-500">Apply writes MUSICBRAINZ_ALBUMID, the release group and album artist IDs and links to every file, and MUSICBRAINZ_ARTISTID and its link to each assigned file. With “Import song titles” on, assigned files also get the release's TITLE, ARTIST, TRACKNUMBER, DISCNUMBER and DISCSUBTITLE and are renamed. BARCODE, ASIN, MUSICBRAINZ_ALBUM_RELEASECOUNTRY, MUSICBRAINZ_ALBUMSTATUS, MUSICBRAINZ_ALBUMTYPE and MUSICBRAINZ_ALBUM_DISAMBIGUATION are filled only where the file has none yet.</div>
					</>
				) : rows && <Results rows={rows} sort={sort} setSort={setSort} pick={pick} />}
			</div>
			</div>
		</Shell>
	)
}
