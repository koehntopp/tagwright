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
import { CopyBtn, IdBadge, searchQuery } from '@/components/inspector'
import { TrackTable } from '@/components/track-table'
import { LibraryTab } from '@/components/library'

type Shell = { open: boolean; onClose: () => void; title: React.ReactNode; wide?: string; err?: string; save?: () => void; saveLabel?: string; saveDisabled?: boolean; cancelLabel?: string; children: React.ReactNode; header?: React.ReactNode }
export function Shell({ open, onClose, title, wide = 'sm:max-w-[40rem]', err, save, saveLabel = 'Save', saveDisabled, cancelLabel = 'Cancel', children, header }: Shell) {
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
					<Button variant="outline" size="sm" onClick={onClose}>{cancelLabel}</Button>
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
	useEffect(() => { if (a) { setArtist(a.artist_override || a.artist); setName(a.title_override || a.album); setErr('') } }, [a?.path])  // eslint-disable-line react-hooks/exhaustive-deps  -- by path: a refresh of the album must not overwrite what is being typed
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
	const [s, setS] = useState<any>(null), [f, setF] = useState<any>({}), [lib, setLib] = useState<any>(null), [err, setErr] = useState(''), [tab, setTab] = useState('general')
	useEffect(() => {
		if (!open) return
		api('/api/settings').then(r => { setS(r); setLib(r.library); setF({ min_cover: r.min_cover, discogs_api_key: '' }); setErr(''); setTab('general') }, e => toast.error(e.message))
	}, [open])
	const save = async () => {
		try {
			await post('/api/settings', { ...f, library: { apply: lib.apply, cooldown: +lib.cooldown, interval: +lib.interval, sweep_hours: lib.sweep_hours, template: lib.template } })
			toast.success('Settings saved'); onClose(); saved()
		} catch (e: any) { setErr(e.message) }
	}
	const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value })
	return (
		<Shell open={open && !!s} onClose={onClose} title="Settings" wide={tab === 'library' ? 'sm:max-w-[56rem]' : 'sm:max-w-[48rem]'} err={err} save={save}
			header={<Tabs value={tab} onValueChange={setTab} className="ml-auto mr-8"><TabsList><TabsTrigger value="general">General</TabsTrigger><TabsTrigger value="library">Library</TabsTrigger></TabsList></Tabs>}>
			{s && tab === 'general' && (
				<div className="space-y-3">
					<Field label="Staging folder" help="Albums to fix are read from here. Set with STAGING_FOLDER."><div className="rounded-md border bg-muted/40 px-3 py-2 font-mono text-sm">{s.input_source || s.input}</div></Field>
					<Field label="Library folder" help="Fixed albums are placed here in the library layout, and a watcher keeps this folder in that layout (see the Library tab). Set with LIBRARY_FOLDER."><div className="rounded-md border bg-muted/40 px-3 py-2 font-mono text-sm">{s.output_source || s.output}</div></Field>
					<Field label="Minimum cover size (pixels)" help="An album whose cover is smaller than this on either side, or has none, cannot be moved to the library. 0 turns the check off."><Input type="number" min={0} max={20000} step={50} className="w-40 font-mono" value={f.min_cover} onChange={set('min_cover')} /></Field>
					<Field label="Discogs API key" help="Leave blank to keep the stored key."><Input type="password" className="font-mono" placeholder={s.discogs_api_key_hint || 'Not set'} value={f.discogs_api_key} onChange={set('discogs_api_key')} /></Field>
				</div>
			)}
			{s && tab === 'library' && lib && <LibraryTab lib={lib} setLib={setLib} />}
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
	}, [target?.path, target?.file])  // eslint-disable-line react-hooks/exhaustive-deps  -- by value: the parent builds a new target object on every render (the library status polls every 3 s)
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

export function TagEditor({ a, tab, reload, onClose, done, begin, openLyrics, openDiscogs, openMb }: {
	a: Album | null; tab: string; reload: number; onClose: () => void; done: (path: string) => void
	begin: (path: string, steps: string[]) => () => void  // marks pipeline steps as working while the save runs; returns the end call
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
		tracks.forEach(x => { const o = d.tracks.find((y: any) => y.file === x.file); if (o && KTRACK.some(([k]) => x[k] !== o[k])) edited.push(x) })
		if (!Object.keys(changed).length && !edited.length) return onClose()
		if ('ALBUM_FORMAT' in changed && !changed.ALBUM_FORMAT.trim()) return setErr('Album format must not be empty (for example CD, SACD, Vinyl).')
		if ('CATALOGNUMBER' in changed && !changed.CATALOGNUMBER.trim()) return setErr("Add a catalog number (enter 'none' if the release has none).")
		if (edited.some(x => !['title', 'disc', 'track'].every(k => String(x[k]).trim()))) return setErr('Title, disc and track must not be empty.')
		// The dialog closes at once; the step circles of the inspector spin until the server answers (a format, catalog # or
		// edition edit rewrites the Discogs tags, ADR 0049, and every save renames the files)
		const end = begin(a.path, ['ALBUM_FORMAT', 'CATALOGNUMBER', 'ALBUM_EDITION'].some(k => k in changed) ? ['Tags and cover', 'Filenames'] : ['Filenames'])
		onClose()
		try { await post('/api/tags', { path: a.path, fields: changed, tracks: edited }); toast.success('Tags saved'); done(a.path) }
		catch (e: any) { toast.error(e.message) }
		finally { end() }
	}
	const mbid = fields.MUSICBRAINZ_ALBUMID
	const dval = (k: string) => d.discogs.find((r: any) => r.key === k)?.value ?? ''
	const discogsTitle = dval('ALBUM_MASTER_TITLE') || dval('ALBUM_RELEASE_TITLE')
	return (
		<Shell open onClose={onClose} wide="sm:max-w-[72rem]" title="Tag editor" err={err} save={save}
			header={
				<Tabs value={t} onValueChange={setT} className="ml-auto mr-8">
					<TabsList><TabsTrigger value="album">Album</TabsTrigger><TabsTrigger value="tracks">Tracks</TabsTrigger><TabsTrigger value="discogs">Discogs</TabsTrigger><TabsTrigger value="musicbrainz">MusicBrainz</TabsTrigger><TabsTrigger value="other">Other</TabsTrigger></TabsList>
				</Tabs>
			}>
			<div className="max-h-[62vh] overflow-y-auto pr-1">
				{t === 'album' && (
					<div className="space-y-4">
						<div className="grid grid-cols-2 gap-x-6 gap-y-4">
							<Field label="Album Artist Override">
								<Input value={fields.ALBUM_ARTIST_OVERRIDE ?? ''} onChange={e => setFields({ ...fields, ALBUM_ARTIST_OVERRIDE: e.target.value })} />
								{d.discogs_id && d.album_artist && <Small>ALBUM ARTIST: {d.album_artist}</Small>}
							</Field>
							<Field label="Album Title Override">
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
							<Field label="Discogs Release ID">
								<div className="flex items-center gap-1 py-1">
									<IdBadge l="D" v={d.discogs_id || ''} full q={searchQuery(a)} />
									<button onClick={openDiscogs} title={d.discogs_id ? 'Change the Discogs release' : 'Choose the Discogs release'} className="rounded-full p-1 hover:bg-slate-100"><Pencil className="size-3.5" /></button>
								</div>
							</Field>
							<Field label="Musicbrainz Release ID">
								<div className="flex items-center gap-1 py-1">
									<IdBadge l="MB" v={mbid || ''} full q={searchQuery(a)} />
									<button onClick={openMb} title={mbid ? 'Change the MusicBrainz release' : 'Choose the MusicBrainz release'} className="rounded-full p-1 hover:bg-slate-100"><Pencil className="size-3.5" /></button>
								</div>
							</Field>
						</div>
					</div>
				)}
				{t === 'tracks' && <TrackTable rows={tracks} setRows={setTracks} openLyrics={file => openLyrics(a.path, file)} />}
				{(t === 'discogs' || t === 'musicbrainz') && (() => {
					const rows: { key: string; value: string }[] = t === 'discogs' ? d.discogs : d.musicbrainz
					return (
						<>
							<p className="mb-3 text-[13px] text-slate-600">{t === 'discogs' ? 'Written from the Discogs release, so edit the release choice rather than these values. The overrides on the Album tab take precedence over ALBUM and ALBUMARTIST.' : 'Written by the MusicBrainz release choice; the release ID itself is on the Album tab.'}</p>
							<table className="w-full text-sm">
								<tbody>
									{rows.length ? rows.map(r => (
										<tr key={r.key} className="border-b text-slate-700"><td className="w-72 py-1 align-top font-mono text-xs">{r.key}</td><td className="whitespace-pre-wrap break-words">{r.value}</td></tr>
									)) : <tr><td className="text-slate-500">{t === 'discogs' ? 'No Discogs tags yet. Run fixes to write them.' : 'No MusicBrainz tags yet. Choose a MusicBrainz release.'}</td></tr>}
								</tbody>
							</table>
						</>
					)
				})()}
				{t === 'other' && (
					<>
						<p className="mb-3 text-[13px] text-slate-600">Every other tag in the files, as the first file has it. Lyrics are edited per track. These are read-only.</p>
						<table className="w-full text-sm">
							<tbody>
								{d.other.length ? d.other.map((r: { key: string; value: string; files: number; of: number; varies: boolean }) => (
									<tr key={r.key} className="border-b text-slate-700">
										<td className="w-72 py-1 align-top font-mono text-xs">{r.key}</td>
										<td className="break-all" title={r.value}><span className="line-clamp-2">{r.value}</span></td>
										<td className="w-36 whitespace-nowrap pl-2 text-right align-top text-xs text-slate-500">{[r.files < r.of ? `${r.files} of ${r.of} files` : '', r.varies ? 'differs' : ''].filter(Boolean).join(' · ')}</td>
									</tr>
								)) : <tr><td className="text-slate-500">No other tags.</td></tr>}
							</tbody>
						</table>
					</>
				)}
			</div>
		</Shell>
	)
}
