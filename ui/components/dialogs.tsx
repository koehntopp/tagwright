'use client'

import { useEffect, useState } from 'react'
import { Pencil } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { Album, api, mmss, post } from '@/lib/api'
import { CopyBtn } from '@/components/inspector'

type Shell = { open: boolean; onClose: () => void; title: React.ReactNode; wide?: string; err?: string; save?: () => void; saveLabel?: string; saveDisabled?: boolean; children: React.ReactNode; header?: React.ReactNode }
export function Shell({ open, onClose, title, wide = 'sm:max-w-[40rem]', err, save, saveLabel = 'Save', saveDisabled, children, header }: Shell) {
	return (
		<Dialog open={open} onOpenChange={o => !o && onClose()}>
			<DialogContent className={`${wide} gap-0 rounded-2xl`}>
				<DialogHeader className="flex-row items-center gap-3">
					<DialogTitle className="text-lg">{title}</DialogTitle>
					{header}
				</DialogHeader>
				<div className="mt-3">{children}</div>
				{err && <p className="mt-2 text-sm text-rose-600">{err}</p>}
				<DialogFooter className="mt-4">
					<Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
					{save && <Button size="sm" className="bg-slate-800 text-white hover:bg-slate-700" disabled={saveDisabled} onClick={save}>{saveLabel}</Button>}
				</DialogFooter>
			</DialogContent>
		</Dialog>
	)
}

const Small = ({ children }: { children: React.ReactNode }) => <p className="text-[11px] leading-snug text-slate-500">{children}</p>
const Field = ({ label, help, children }: { label: string; help?: string; children: React.ReactNode }) => (
	<div className="space-y-1">
		<div className="text-sm font-medium">{label}</div>
		{children}
		{help && <p className="text-xs text-slate-500">{help}</p>}
	</div>
)

export function CoverDelete({ open, onClose, onOk, err }: { open: boolean; onClose: () => void; onOk: () => void; err: string }) {
	return (
		<Shell open={open} onClose={onClose} title="Remove cover?" wide="sm:max-w-[24rem]" err={err} save={onOk} saveLabel="Remove cover">
			<p className="text-sm">The embedded cover is removed from every file of this album, and a cover.jpg or folder image in the album folder is deleted.</p>
		</Shell>
	)
}

export function AlbumEdit({ a, onClose, done }: { a: Album | null; onClose: () => void; done: (path: string) => void }) {
	const [artist, setArtist] = useState(''), [name, setName] = useState(''), [err, setErr] = useState('')
	useEffect(() => { if (a) { setArtist(a.artist_override || a.artist); setName(a.title_override || a.album); setErr('') } }, [a])
	if (!a) return null
	const save = async () => {
		const ar = artist.trim(), ti = name.trim()
		try {
			await post('/api/overrides', { path: a.path, artist: ar === a.artist && !a.artist_override ? '' : ar, title: ti === a.album && !a.title_override ? '' : ti })
			toast.success('Album saved'); onClose(); done(a.path)
		} catch (e: any) { setErr(e.message) }
	}
	return (
		<Shell open onClose={onClose} title="Edit album" err={err} save={save}>
			<div className="space-y-3">
				<Field label="Album artist" help="Saved as ALBUM_ARTIST_OVERRIDE and used instead of the Discogs artist. Empty removes the override and restores the Discogs artist.">
					<div className="flex items-center gap-1"><Input value={artist} onChange={e => setArtist(e.target.value)} /><CopyBtn text={artist} /></div>
				</Field>
				<Field label="Album title" help="Saved as ALBUM_TITLE_OVERRIDE and used instead of the Discogs title. Empty removes the override and restores the Discogs master title.">
					<div className="flex items-center gap-1"><Input value={name} onChange={e => setName(e.target.value)} /><CopyBtn text={name} /></div>
				</Field>
			</div>
		</Shell>
	)
}

export function SettingsDialog({ open, onClose, saved }: { open: boolean; onClose: () => void; saved: () => void }) {
	const [s, setS] = useState<any>(null), [f, setF] = useState<any>({}), [err, setErr] = useState('')
	useEffect(() => {
		if (!open) return
		api('/api/settings').then(r => { setS(r); setF({ input: r.input, output: r.output, min_cover: r.min_cover, discogs_api_key: '', lrclib_api_key: '' }); setErr('') }, e => toast.error(e.message))
	}, [open])
	const save = async () => {
		try { await post('/api/settings', { ...f, input: f.input.trim(), output: f.output.trim() }); toast.success('Settings saved'); onClose(); saved() }
		catch (e: any) { setErr(e.message) }
	}
	const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value })
	return (
		<Shell open={open && !!s} onClose={onClose} title="Settings" wide="sm:max-w-[48rem]" err={err} save={save}>
			{s && (
				<div className="space-y-3">
					<Field label="Input folder" help="Albums to fix are read from here."><Input className="font-mono" value={f.input} onChange={set('input')} /></Field>
					<Field label="Output folder" help="Fixed albums are moved here."><Input className="font-mono" value={f.output} onChange={set('output')} /></Field>
					<Field label="Minimum cover size (pixels)" help="An album whose cover is smaller than this on either side, or has none, cannot be moved to ingest. 0 turns the check off."><Input type="number" min={0} max={20000} step={50} className="w-40 font-mono" value={f.min_cover} onChange={set('min_cover')} /></Field>
					<Field label="Discogs API key" help="Leave blank to keep the stored key."><Input type="password" className="font-mono" placeholder={s.discogs_api_key_hint || 'Not set'} value={f.discogs_api_key} onChange={set('discogs_api_key')} /></Field>
					<Field label="lrclib.net API key" help="Optional. Stored and passed to the scripts as lrclib_api_key."><Input type="password" className="font-mono" placeholder={s.lrclib_api_key_hint || 'Not set'} value={f.lrclib_api_key} onChange={set('lrclib_api_key')} /></Field>
				</div>
			)}
		</Shell>
	)
}

const MARK = { instr: '[00:00.00] [Instrumental]', intro: '[00:00.00](Spoken Intro)' }
export function LyricsEdit({ target, onClose, done }: { target: { path: string; file: string } | null; onClose: () => void; done: (path: string) => void }) {
	const [t, setT] = useState<any>(null), [title, setTitle] = useState(''), [artist, setArtist] = useState(''), [text, setText] = useState('')
	const [res, setRes] = useState<any[] | string | null>(null), [used, setUsed] = useState(-1), [err, setErr] = useState(''), [busy, setBusy] = useState(false)
	useEffect(() => {
		if (!target) return
		setRes(null); setUsed(-1); setErr('')
		api(`/api/track?path=${encodeURIComponent(target.path)}&file=${encodeURIComponent(target.file)}`).then(r => { setT(r); setTitle(r.title); setArtist(r.artist); setText(r.lyrics) }, e => { toast.error(e.message); onClose() })
	}, [target])  // eslint-disable-line react-hooks/exhaustive-deps
	if (!target || !t) return null
	const synced = /^\s*\[\d+:\d+(\.\d+)?\]/m.test(text), n = text.trim() ? text.replace(/\n+$/, '').split('\n').length : 0
	const near = (x: any) => Math.abs(x.duration - t.length)
	const search = async () => {
		setBusy(true); setRes('Searching lrclib.net...')
		try {
			let r: any[] = await api('/api/lrclib/search?' + new URLSearchParams({ title, artist }))
			if (t.length) r = r.sort((a, b) => near(a) - near(b))
			setRes(r); setUsed(-1)
		} catch (e: any) { setRes('!' + e.message) }
		setBusy(false)
	}
	const save = async () => {
		try { const d = await post('/api/track', { path: target.path, file: target.file, lyrics: text }); toast.success('Track saved'); onClose(); done(target.path); void d }
		catch (e: any) { setErr(e.message) }
	}
	const onEnter = (e: React.KeyboardEvent) => { if (e.key === 'Enter') { e.preventDefault(); search() } }
	return (
		<Shell open onClose={onClose} wide="sm:max-w-[72rem]" title="Edit lyrics" err={err} save={save}
			header={<div className="min-w-0 truncate font-mono text-xs text-slate-500">{target.file} {t.length ? <Badge variant="secondary" className="ml-1">{mmss(t.length)}</Badge> : null}</div>}>
			<div className="flex items-center gap-2 rounded-xl bg-slate-100 p-2">
				<Input className="h-8 flex-1" value={title} onChange={e => setTitle(e.target.value)} onKeyDown={onEnter} placeholder="title to search for" />
				<Input className="h-8 flex-1" value={artist} onChange={e => setArtist(e.target.value)} onKeyDown={onEnter} placeholder="artist to search for" />
				<Button size="sm" className="bg-slate-800 text-white hover:bg-slate-700" disabled={busy} onClick={search} title="Search lrclib.net with this title and artist (not saved)">
					{/* eslint-disable-next-line @next/next/no-img-element */}
					<img src="/static/lrclib.ico" alt="" className="size-3.5" />Search lrclib.net
				</Button>
			</div>
			<div className="mb-1 mt-4 flex items-center gap-2">
				<span className="text-sm font-medium">Lyrics</span>
				<span className={`w-16 rounded-full px-2 text-center text-xs font-medium ${!n ? 'bg-slate-200' : synced ? 'bg-emerald-500 text-white' : 'bg-amber-400'}`}>{!n ? 'Empty' : synced ? 'LRC' : 'TXT'}</span>
				<span className="text-xs text-slate-500">{n ? `${n} line${n > 1 ? 's' : ''}` : ''}</span>
				<div className="ml-auto flex gap-2">
					<Button size="xs" variant="ghost" onClick={() => setText(MARK.instr)}>Instrumental</Button>
					<Button size="xs" variant="ghost" onClick={() => setText(MARK.intro)}>Spoken Intro</Button>
				</div>
			</div>
			<div className="flex items-stretch gap-3">
				<Textarea value={text} onChange={e => setText(e.target.value)} spellCheck={false} className="h-[60vh] min-h-72 min-w-0 flex-1 font-mono text-xs leading-relaxed" placeholder="Plain text (TXT) or synced [mm:ss.xx] lines (LRC). Empty removes the lyrics." />
				{res && (
					<div className="h-[60vh] min-h-72 w-[26rem] shrink-0 divide-y overflow-y-auto rounded-lg border text-xs">
						{typeof res === 'string' ? <div className={`p-3 ${res[0] === '!' ? 'text-rose-600' : 'text-slate-500'}`}>{res.replace(/^!/, '')}</div>
							: !res.length ? <div className="p-3 text-slate-500">No results.</div> : (
								<>
									<div className="sticky top-0 z-10 bg-slate-100 px-2 py-1 font-medium text-slate-600">{res.length} result{res.length > 1 ? 's' : ''} on lrclib.net</div>
									{res.map((x, i) => (
										<div key={i} className={`p-2 ${t.length && near(x) <= 3 ? 'bg-emerald-50' : 'hover:bg-slate-50'} ${used === i ? 'ring-2 ring-inset ring-slate-400' : ''}`}>
											<div className="flex items-center gap-2">
												<Badge variant="secondary" className="w-10 shrink-0 justify-center">{mmss(x.duration)}</Badge>
												<div className="min-w-0 flex-1"><div className="truncate font-medium">{x.artist} - {x.title}</div><div className="truncate text-slate-500">{x.album}</div></div>
											</div>
											<div className="mt-1 flex justify-end gap-1">
												{x.synced && <Button size="xs" className="bg-emerald-500 text-white hover:bg-emerald-600" onClick={() => { setText(x.synced); setUsed(i) }}>LRC</Button>}
												{x.plain && <Button size="xs" className="bg-amber-400 text-amber-950 hover:bg-amber-500" onClick={() => { setText(x.plain); setUsed(i) }}>TXT</Button>}
												{x.instrumental && <Button size="xs" variant="outline" onClick={() => { setText(MARK.instr); setUsed(i) }}>Instrumental</Button>}
											</div>
										</div>
									))}
								</>
							)}
					</div>
				)}
			</div>
			<p className="mt-2 text-xs text-slate-500">Title and artist are only used for the search and are not saved (change them in the Tag Editor).</p>
		</Shell>
	)
}

const KTRACK: [string, string, string][] = [['disc', 'Disc', 'w-14'], ['track', 'Track', 'w-14'], ['title', 'Title', 'min-w-40'], ['artist', 'Artist', 'min-w-32'], ['subtitle', 'Disc subtitle', 'min-w-28']]

export function TagEditor({ a, tab, reload, onClose, done, openLyrics, openDiscogs, openMb }: {
	a: Album | null; tab: string; reload: number; onClose: () => void; done: (path: string) => void
	openLyrics: (path: string, file: string) => void; openDiscogs: () => void; openMb: () => void
}) {
	const [d, setD] = useState<any>(null), [fields, setFields] = useState<Record<string, string>>({}), [tracks, setTracks] = useState<any[]>([]), [t, setT] = useState('album'), [err, setErr] = useState('')
	useEffect(() => {
		if (!a) return
		api('/api/tags?path=' + encodeURIComponent(a.path)).then(r => { setD(r); setFields({ ...r.fields }); setTracks(r.tracks.map((x: any) => ({ ...x }))); setErr('') }, e => { toast.error(e.message); onClose() })
	}, [a?.path, reload])  // eslint-disable-line react-hooks/exhaustive-deps
	useEffect(() => { setT(tab) }, [tab, a?.path])
	if (!a || !d) return null
	const save = async () => {
		const changed: Record<string, string> = {}, edited: any[] = []
		Object.keys(fields).forEach(k => { if (fields[k].trim() !== d.fields[k]) changed[k] = fields[k] })
		tracks.forEach((x, i) => { if (KTRACK.some(([k]) => x[k] !== d.tracks[i][k])) edited.push(x) })
		if (!Object.keys(changed).length && !edited.length) return onClose()
		if ('ALBUM_FORMAT' in changed && !changed.ALBUM_FORMAT.trim()) return setErr('Album format must not be empty (for example CD, SACD, Vinyl).')
		if ('CATALOGNUMBER' in changed && !changed.CATALOGNUMBER.trim()) return setErr("Add a catalog number (enter 'none' if the release has none).")
		if (edited.some(x => !['title', 'disc', 'track'].every(k => String(x[k]).trim()))) return setErr('Title, disc and track must not be empty.')
		try { await post('/api/tags', { path: a.path, fields: changed, tracks: edited }); toast.success('Tags saved'); onClose(); done(a.path) }
		catch (e: any) { setErr(e.message) }
	}
	const mbid = fields.MUSICBRAINZ_ALBUMID
	const dval = (k: string) => d.discogs.find((r: any) => r.key === k)?.value ?? ''
	const discogsTitle = dval('ALBUM_MASTER_TITLE') || dval('ALBUM_RELEASE_TITLE')
	return (
		<Shell open onClose={onClose} wide="sm:max-w-[72rem]" title="Tag editor" err={err} save={save}
			header={
				<Tabs value={t} onValueChange={setT} className="ml-auto">
					<TabsList><TabsTrigger value="album">Album</TabsTrigger><TabsTrigger value="tracks">Tracks</TabsTrigger><TabsTrigger value="discogs">Discogs / Musicbrainz</TabsTrigger></TabsList>
				</Tabs>
			}>
			<div className="max-h-[62vh] overflow-y-auto pr-1">
				{t === 'album' && (
					<div className="space-y-4">
						<div className="grid grid-cols-2 gap-x-6 gap-y-4">
							<Field label="Album Artist Override" help="Written to ALBUMARTIST on every fix and used in the folder name. Empty: remove the override and restore the Discogs artist.">
								<Input value={fields.ALBUM_ARTIST_OVERRIDE ?? ''} onChange={e => setFields({ ...fields, ALBUM_ARTIST_OVERRIDE: e.target.value })} />
								{d.discogs_id && d.album_artist && <Small>ALBUM ARTIST: {d.album_artist}</Small>}
							</Field>
							<Field label="Album Title Override" help="Replaces the Discogs title. Empty: remove the override and restore the Discogs master title.">
								<Input value={fields.ALBUM_TITLE_OVERRIDE ?? ''} onChange={e => setFields({ ...fields, ALBUM_TITLE_OVERRIDE: e.target.value })} />
								{d.discogs_id && discogsTitle && <Small>ALBUM TITLE: {discogsTitle}</Small>}
							</Field>
							<Field label="Album Format" help="For example CD, SACD, Vinyl. Required."><Input value={fields.ALBUM_FORMAT ?? ''} onChange={e => setFields({ ...fields, ALBUM_FORMAT: e.target.value })} /></Field>
							<Field label="Album Edition" help="For example Remastered or Gold Disc. Part of the version string."><Input value={fields.ALBUM_EDITION ?? ''} onChange={e => setFields({ ...fields, ALBUM_EDITION: e.target.value })} /></Field>
						</div>
						<div className="grid grid-cols-3 gap-x-6">
							<Field label="Catalog #" help="Part of the version string. Enter 'none' if the release has none."><Input value={fields.CATALOGNUMBER ?? ''} onChange={e => setFields({ ...fields, CATALOGNUMBER: e.target.value })} /></Field>
							<Field label="Year Release" help="From Discogs, read-only."><Input readOnly tabIndex={-1} className="bg-slate-50 text-slate-600" value={dval('ALBUM_RELEASE_YEAR')} /></Field>
							<Field label="Year Master Release" help="From Discogs, read-only."><Input readOnly tabIndex={-1} className="bg-slate-50 text-slate-600" value={dval('ALBUM_MASTER_YEAR')} /></Field>
						</div>
						<div className="grid grid-cols-2 gap-x-6">
							<Field label="Discogs Release ID" help="Changed only through the release dialog, which also assigns the tracks.">
								<div className="flex items-center gap-2">
									<Input readOnly tabIndex={-1} className="bg-slate-50 font-mono" value={d.discogs_id || ''} placeholder="missing" />
									{d.discogs_id && <a className="shrink-0 text-xs text-sky-700 underline" href={`https://www.discogs.com/release/${d.discogs_id}`} target="_blank" rel="noopener">open</a>}
									<Button size="sm" variant="outline" className="shrink-0" onClick={openDiscogs}>{d.discogs_id ? 'Change release…' : 'Choose release…'}</Button>
								</div>
							</Field>
							<Field label="Musicbrainz Release ID" help="Anchors the language tags to a MusicBrainz release.">
								<div className="flex items-center gap-2">
									<Input className="font-mono" value={mbid ?? ''} onChange={e => setFields({ ...fields, MUSICBRAINZ_ALBUMID: e.target.value })} />
									{mbid && <a className="shrink-0 text-xs text-sky-700 underline" href={`https://musicbrainz.org/release/${mbid}`} target="_blank" rel="noopener">open</a>}
									<Button size="sm" variant="outline" className="shrink-0" onClick={openMb}>{mbid ? 'Change release…' : 'Choose release…'}</Button>
								</div>
							</Field>
						</div>
					</div>
				)}
				{t === 'tracks' && (
					<table className="w-full text-sm">
						<thead><tr className="text-left text-xs text-slate-500">{KTRACK.map(c => <th key={c[0]} className="pb-1 font-medium">{c[1]}</th>)}<th /></tr></thead>
						<tbody>
							{tracks.map((x, i) => (
								<tr key={x.file}>
									{KTRACK.map(([k, , w]) => (
										<td key={k} className="pr-2 pb-1"><Input className={`h-7 text-xs ${w}`} value={x[k] ?? ''} onChange={e => setTracks(tracks.map((y, j) => (j === i ? { ...y, [k]: e.target.value } : y)))} /></td>
									))}
									<td><button className="rounded-full p-1 hover:bg-slate-100" title="Edit lyrics" onClick={() => openLyrics(a.path, x.file)}><Pencil className="size-3" /></button></td>
								</tr>
							))}
						</tbody>
					</table>
				)}
				{t === 'discogs' && (
					<>
						<p className="mb-3 text-[13px] text-slate-600">Written from the Discogs and MusicBrainz releases, so edit the release choice rather than these values. The overrides on the Album tab take precedence over ALBUM and ALBUMARTIST.</p>
						{([['Discogs', d.discogs, 'No Discogs tags yet. Run fixes to write them.'], ['MusicBrainz', d.musicbrainz, 'No MusicBrainz tags yet. Choose a MusicBrainz release.']] as [string, { key: string; value: string }[], string][]).map(([name, rows, none]) => (
							<div key={name} className="mb-4">
								<h4 className="mb-1 text-xs font-medium uppercase tracking-wider text-slate-500">{name}</h4>
								<table className="w-full text-sm">
									<tbody>
										{rows.length ? rows.map(r => (
											<tr key={r.key} className="border-b text-slate-700"><td className="w-72 py-1 align-top font-mono text-xs">{r.key}</td><td className="whitespace-pre-wrap break-words">{r.value}</td></tr>
										)) : <tr><td className="text-slate-500">{none}</td></tr>}
									</tbody>
								</table>
							</div>
						))}
					</>
				)}
			</div>
		</Shell>
	)
}
