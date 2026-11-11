'use client'

import { useCallback, useEffect, useState } from 'react'
import { GripVertical, Plus, RotateCw, X } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Shell } from '@/components/dialogs'
import { Chip, LibraryStatus, Tpl, api, post } from '@/lib/api'

const ago = (t: number) => {
	if (!t) return 'never'
	const s = Math.max(0, Math.round(Date.now() / 1000 - t))
	return s < 90 ? `${s} s ago` : s < 5400 ? `${Math.round(s / 60)} min ago` : `${Math.round(s / 3600)} h ago`
}
const n = (x: number) => x.toLocaleString('en-US')
const plural = (x: number, one: string, many = one + 's') => `${n(x)} ${x === 1 ? one : many}`

export function useLibrary() {
	const [st, setSt] = useState<LibraryStatus | null>(null)
	const load = useCallback(async () => { try { setSt(await api('/api/library')) } catch { /* the server restarts now and then */ } }, [])
	useEffect(() => {
		let live = true
		const tick = async () => { if (live) await load() }
		void tick()
		const id = setInterval(() => void tick(), 3000)
		return () => { live = false; clearInterval(id) }
	}, [load])
	return { st, reload: load }
}

function describe(st: LibraryStatus) {
	if (st.phase === 'error') return { dot: 'bg-rose-500', text: st.error || 'Error' }
	if (st.phase === 'scanning' || st.phase === 'planning') return { dot: 'animate-pulse bg-sky-500', text: st.message || 'Scanning…' }
	if (st.phase === 'moving') return { dot: 'animate-pulse bg-sky-500', text: st.message || 'Moving files…' }
	if (!st.apply && st.planned.length) return { dot: 'bg-amber-500', text: `Report only: ${st.planned.length} move${st.planned.length > 1 ? 's' : ''} planned` }
	if (st.phase === 'waiting') return { dot: 'bg-amber-500', text: st.message || 'Waiting for files to settle' }
	if (st.unplaced.length) return { dot: 'bg-amber-500', text: `${st.unplaced.length} file${st.unplaced.length > 1 ? 's' : ''} cannot be placed` }
	return { dot: 'bg-emerald-500', text: st.phase === 'starting' ? 'Starting…' : 'Up to date' }
}

export function LibraryIndicator({ st, open }: { st: LibraryStatus | null; open: () => void }) {
	if (!st) return <div className="flex-1 text-xs text-slate-400">Library…</div>
	const d = describe(st)
	return (
		<button onClick={open} title="Library status" className="flex min-w-0 flex-1 items-center gap-2 rounded-lg px-1 py-1 text-left text-xs hover:bg-white/60">
			<span className={`size-2 shrink-0 rounded-full ${d.dot}`} />
			<div className="min-w-0 flex-1 leading-tight">
				<div className="truncate font-medium">{plural(st.artists, 'artist')} · {plural(st.albums, 'album')} · {plural(st.tracks, 'track')}</div>
				<div className="truncate text-slate-500">{d.text}</div>
			</div>
		</button>
	)
}

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
	<div className="mt-4 first:mt-0">
		<h4 className="mb-1 text-xs font-medium uppercase tracking-wider text-slate-500">{title}</h4>
		{children}
	</div>
)
const Row = ({ a, b }: { a: string; b?: string }) => (
	<li className="grid grid-cols-[1fr] gap-0 border-b border-slate-100 py-1 text-xs last:border-0">
		<span className="truncate font-mono" title={a}>{a}</span>
		{b && <span className="truncate text-slate-500" title={b}>{b}</span>}
	</li>
)

export function LibraryDialog({ open, onClose, st, reload }: { open: boolean; onClose: () => void; st: LibraryStatus | null; reload: () => void }) {
	const [busy, setBusy] = useState(false)
	if (!st) return null
	const d = describe(st)
	const rescan = async () => {
		setBusy(true)
		try { await post('/api/library/rescan', {}); toast.success('Re-analysis started'); reload() } catch (e: any) { toast.error(e.message) }
		setBusy(false)
	}
	return (
		<Shell open={open} onClose={onClose} title="Library" cancelLabel="Close" wide="sm:max-w-[40rem]" header={<span className={`size-2 rounded-full ${d.dot}`} />}>
			<div className="grid grid-cols-3 gap-2 text-center">
				{[['Album artists', st.artists], ['Albums', st.albums], ['Tracks', st.tracks]].map(([l, v]) => (
					<div key={l as string} className="rounded-xl bg-slate-100 py-2"><div className="text-xl font-semibold">{n(v as number)}</div><div className="text-xs text-slate-500">{l}</div></div>
				))}
			</div>
			<p className="mt-3 text-sm">{d.text}</p>
			<p className="mt-1 break-all font-mono text-[11px] text-slate-500">{st.root}</p>
			<p className="mt-1 text-xs text-slate-500">Last scan {ago(st.last_scan)}, last full pass {ago(st.last_full)}. {st.apply ? `Changes are applied after ${st.cooldown} s without any change.` : 'Report only: nothing is moved (turn on Apply in Settings, Library).'}</p>
			<div className="mt-3 max-h-[45vh] overflow-y-auto pr-1">
				{st.recent.length > 0 && <Section title="Recent activity"><ul>{st.recent.slice(0, 15).map((r, i) => <Row key={i} a={r.text} b={ago(r.t)} />)}</ul></Section>}
				{st.planned.length > 0 && <Section title={st.apply ? `Waiting to move (${st.waiting})` : `Planned moves (${st.planned.length})`}><ul>{st.planned.slice(0, 20).map(m => <Row key={m.from} a={m.from} b={'→ ' + m.to} />)}</ul></Section>}
				{st.unplaced.length > 0 && <Section title={`Cannot be placed (${st.unplaced.length})`}><ul>{st.unplaced.slice(0, 30).map(u => <Row key={u.path} a={u.path} b={u.reason} />)}</ul></Section>}
				{st.skipped.length > 0 && <Section title={`Skipped, conflicting names (${st.skipped.length})`}><ul>{st.skipped.slice(0, 30).map(u => <Row key={u.path} a={u.path} b={u.reason} />)}</ul></Section>}
			</div>
			<div className="mt-4 flex items-center gap-2">
				<Button size="sm" variant="outline" disabled={busy} onClick={rescan} title="Forget what is known about the folders and read everything again"><RotateCw className="size-3.5" />Re-analyze</Button>
				<span className="text-xs text-slate-500">Lists every folder and file again; a large library takes a while.</span>
			</div>
		</Shell>
	)
}

// ---- Settings: the Library tab ----

type Pal = { key: string; label: string }
type Drag = { src: string; idx: number; chip: Chip }
const FORMATS: Record<string, string> = { text: 'Text', num: 'Number, zero-padded', int: 'Number', year: 'Year (4 digits)' }
const clone = (t: Tpl): Tpl => JSON.parse(JSON.stringify(t))
const rowOf = (t: Tpl, key: string): Chip[] => (key === 'file' ? t.filename : key === 'disc' ? t.disc_folder! : t.folders[+key.slice(1)])

export function LibraryTab({ lib, setLib }: { lib: any; setLib: (l: any) => void }) {
	const tpl: Tpl = lib.template, pal: Pal[] = lib.palette
	const label = (k?: string) => pal.find(p => p.key === k)?.label || k || ''
	const [drag, setDrag] = useState<Drag | null>(null), [over, setOver] = useState<string>(''), [sel, setSel] = useState<{ row: string; idx: number } | null>(null)
	const [prev, setPrev] = useState<any>(null)
	const setTpl = (t: Tpl) => setLib({ ...lib, template: t })
	const mutate = (fn: (t: Tpl) => void) => { const t = clone(tpl); fn(t); setTpl(t) }

	useEffect(() => {
		const id = setTimeout(() => { post('/api/library/preview', { template: tpl }).then(setPrev, () => setPrev(null)) }, 400)
		return () => clearTimeout(id)
	}, [tpl])

	const drop = (row: string, at: number) => {
		const d = drag
		setDrag(null); setOver('')
		if (!d) return
		mutate(t => {
			if (d.src !== 'palette') {
				const src = rowOf(t, d.src)
				src.splice(d.idx, 1)
				if (d.src === row && d.idx < at) at -= 1
			}
			rowOf(t, row).splice(at, 0, d.chip)
		})
		setSel(null)
	}
	const rows = [...tpl.folders.map((_, i) => ({ key: 'f' + i, name: `Folder level ${i + 1}` })), ...(tpl.disc_folder ? [{ key: 'disc', name: 'Disc folder (multi-disc albums only)' }] : []), { key: 'file', name: 'File name (.flac is added)' }]
	const chipText = (c: Chip) => (c.tag ? label(c.tag) + (c.fmt && c.fmt !== 'text' ? ` · ${c.fmt === 'num' ? `#${c.pad || ''}` : c.fmt}` : '') + (c.fallback ? ` / ${label(c.fallback)}` : '') : `“${c.text}”`)
	const selChip = sel ? rowOf(tpl, sel.row)?.[sel.idx] : undefined
	const patch = (p: Partial<Chip>) => sel && mutate(t => { Object.assign(rowOf(t, sel.row)[sel.idx], p) })
	const field = 'h-8 rounded-md border border-slate-300 bg-white px-2 text-sm'

	return (
		<div className="space-y-4">
			<div className="grid grid-cols-3 gap-3">
				<label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={lib.apply} onChange={e => setLib({ ...lib, apply: e.target.checked })} /> Apply changes</label>
				<label className="flex items-center gap-2 text-sm">Cooldown (s)<Input type="number" min={0} className="h-8 w-20" value={lib.cooldown} onChange={e => setLib({ ...lib, cooldown: e.target.value })} /></label>
				<label className="flex items-center gap-2 text-sm">Check every (s)<Input type="number" min={10} className="h-8 w-20" value={lib.interval} onChange={e => setLib({ ...lib, interval: e.target.value })} /></label>
			</div>
			<p className="-mt-2 text-xs text-slate-500">With Apply off the library only reports what it would move. A file is acted on only after nothing in its folder has changed for the cooldown.</p>

			<div>
				<div className="mb-1 text-sm font-medium">Tags <span className="font-normal text-slate-500">(drag into a row below)</span></div>
				<div className="flex flex-wrap gap-1.5">
					{pal.map(p => <span key={p.key} draggable onDragStart={() => setDrag({ src: 'palette', idx: 0, chip: { tag: p.key, fmt: p.key === 'DISCNUMBER' || p.key === 'TRACKNUMBER' ? 'num' : p.key === 'DATE' || p.key === 'ORIGINALDATE' ? 'year' : 'text', pad: p.key === 'DISCNUMBER' || p.key === 'TRACKNUMBER' ? 2 : 0 } })} className="inline-flex cursor-grab items-center gap-1 rounded-full border border-slate-300 bg-white px-2.5 py-0.5 text-xs hover:bg-slate-50"><GripVertical className="size-3 text-slate-400" />{p.label}</span>)}
					<span draggable onDragStart={() => setDrag({ src: 'palette', idx: 0, chip: { text: '_' } })} className="inline-flex cursor-grab items-center gap-1 rounded-full border border-dashed border-slate-400 bg-white px-2.5 py-0.5 text-xs hover:bg-slate-50"><GripVertical className="size-3 text-slate-400" />Text</span>
				</div>
			</div>

			<div className="space-y-2">
				{rows.map(r => {
					const chips = rowOf(tpl, r.key)
					return (
						<div key={r.key} className="flex items-center gap-2">
							<div className="w-44 shrink-0 text-xs text-slate-600">{r.name}</div>
							<div onDragOver={e => { e.preventDefault(); setOver(r.key) }} onDragLeave={() => setOver('')} onDrop={e => { e.preventDefault(); drop(r.key, chips.length) }}
								className={`flex min-h-9 flex-1 flex-wrap items-center gap-1 rounded-lg border px-1.5 py-1 ${over === r.key ? 'border-sky-400 bg-sky-50' : 'border-slate-300 bg-slate-50'}`}>
								{chips.length === 0 && <span className="px-1 text-xs text-slate-400">drop tags here</span>}
								{chips.map((c, i) => (
									<span key={i} draggable onDragStart={() => setDrag({ src: r.key, idx: i, chip: c })} onDragOver={e => { e.preventDefault(); e.stopPropagation(); setOver(r.key) }} onDrop={e => { e.preventDefault(); e.stopPropagation(); drop(r.key, i) }} onClick={() => setSel(sel?.row === r.key && sel.idx === i ? null : { row: r.key, idx: i })}
										className={`inline-flex cursor-grab items-center gap-1 rounded-full px-2.5 py-0.5 text-xs ${c.tag ? 'bg-slate-800 text-white' : 'border border-dashed border-slate-400 bg-white'} ${sel?.row === r.key && sel.idx === i ? 'ring-2 ring-sky-400' : ''}`}>
										{chipText(c)}
										<button title="Remove" onClick={e => { e.stopPropagation(); mutate(t => { rowOf(t, r.key).splice(i, 1) }); setSel(null) }} className="opacity-60 hover:opacity-100"><X className="size-3" /></button>
									</span>
								))}
							</div>
							{r.key.startsWith('f') && tpl.folders.length > 1 && <button title="Remove this level" onClick={() => { mutate(t => { t.folders.splice(+r.key.slice(1), 1) }); setSel(null) }} className="text-slate-400 hover:text-rose-600"><X className="size-4" /></button>}
							{r.key === 'disc' && <button title="No disc folder" onClick={() => { mutate(t => { t.disc_folder = null }); setSel(null) }} className="text-slate-400 hover:text-rose-600"><X className="size-4" /></button>}
						</div>
					)
				})}
				<div className="flex gap-2 pl-[11.5rem]">
					{tpl.folders.length < 4 && <Button size="xs" variant="outline" onClick={() => mutate(t => { t.folders.push([]) })}><Plus className="size-3" />Folder level</Button>}
					{!tpl.disc_folder && <Button size="xs" variant="outline" onClick={() => mutate(t => { t.disc_folder = [{ text: 'Disc ' }, { tag: 'DISCNUMBER', fmt: 'int' }] })}><Plus className="size-3" />Disc folder</Button>}
					<Button size="xs" variant="ghost" onClick={() => { setTpl(clone(lib.default_template)); setSel(null) }}>Reset to bliss default</Button>
				</div>
			</div>

			{selChip && (
				<div className="flex flex-wrap items-center gap-3 rounded-lg bg-slate-100 p-2 text-sm">
					{selChip.tag ? (<>
						<span className="font-medium">{label(selChip.tag)}</span>
						<label className="flex items-center gap-1">Format<select className={field} value={selChip.fmt || 'text'} onChange={e => patch({ fmt: e.target.value })}>{Object.entries(FORMATS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
						{selChip.fmt === 'num' && <label className="flex items-center gap-1">Digits<Input type="number" min={0} max={6} className="h-8 w-16" value={selChip.pad || 0} onChange={e => patch({ pad: +e.target.value })} /></label>}
						<label className="flex items-center gap-1" title="Used when this tag is empty. Off by default: an empty tag keeps the file where it is.">If empty use<select className={field} value={selChip.fallback || ''} onChange={e => patch({ fallback: e.target.value })}><option value="">nothing (file stays)</option>{pal.filter(p => p.key !== selChip.tag).map(p => <option key={p.key} value={p.key}>{p.label}</option>)}</select></label>
					</>) : (<label className="flex items-center gap-2">Text<Input className="h-8 w-40 font-mono" value={selChip.text} onChange={e => patch({ text: e.target.value })} /></label>)}
				</div>
			)}

			{prev && (
				<div className="rounded-lg border border-slate-200 p-2 text-xs">
					<div className="mb-1 font-medium">Preview{prev.album && prev.album !== '.' ? <span className="font-normal text-slate-500"> · from {prev.album}</span> : null}</div>
					{prev.errors?.map((e: string) => <p key={e} className="text-rose-600">{e}</p>)}
					{prev.warnings?.map((e: string) => <p key={e} className="text-amber-600">{e}</p>)}
					{prev.album_dir && (
						<div className="mt-1 grid grid-cols-[5.5rem_1fr] gap-x-2 gap-y-0.5">
							<span className="text-slate-500">Album folder</span>
							<span className="break-all font-mono">{prev.album_dir}/</span>
							<span className="text-slate-500">File names</span>
							<ul className="max-h-40 space-y-0.5 overflow-y-auto font-mono">
								{prev.files?.filter((f: any) => f.name).slice(0, 12).map((f: any) => <li key={f.from} className="truncate" title={f.to}>{f.name}</li>)}
							</ul>
						</div>
					)}
					{prev.files?.some((f: any) => f.problem) && (
						<ul className="mt-1 space-y-0.5 font-mono text-amber-600">
							{prev.files.filter((f: any) => f.problem).slice(0, 4).map((f: any) => <li key={f.from} className="truncate" title={f.from}>{f.from.split('/').pop()}: {f.problem}</li>)}
						</ul>
					)}
					{!prev.files?.length && !prev.errors?.length && <p className="text-slate-400">No albums in the library yet.</p>}
				</div>
			)}
		</div>
	)
}
