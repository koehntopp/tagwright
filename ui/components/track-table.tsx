'use client'

import { useState } from 'react'
import { GripVertical, Pencil } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export type Row = { file: string; title: string; artist: string; disc: string; track: string; subtitle: string }
const COLS: [keyof Row, string, string][] = [['disc', 'Disc', 'w-14'], ['track', 'Track', 'w-14'], ['title', 'Title', 'min-w-40'], ['artist', 'Artist', 'min-w-32'], ['subtitle', 'Disc subtitle', 'min-w-28']]
const SETTABLE: [keyof Row, string][] = [['disc', 'Disc'], ['subtitle', 'Disc subtitle'], ['artist', 'Artist'], ['track', 'Track']]

// Track list of the tag editor: shift-click selects a range, bulk set and renumber act on the selection,
// dragging a row (or the selection) reorders; the disc and track numbers stay with the positions ([ADR 0014]).
export function TrackTable({ rows, setRows, openLyrics }: { rows: Row[]; setRows: (r: Row[]) => void; openLyrics: (file: string) => void }) {
	const [sel, setSel] = useState<Set<string>>(new Set())
	const [anchor, setAnchor] = useState<number | null>(null)
	const [field, setField] = useState<keyof Row>('disc')
	const [value, setValue] = useState('')
	const [start, setStart] = useState('1')
	const [drag, setDrag] = useState<string | null>(null)
	const [over, setOver] = useState<number | null>(null)
	const chosen = rows.filter(r => sel.has(r.file))

	const click = (e: React.MouseEvent, i: number) => {
		const next = new Set(sel)
		if (e.shiftKey && anchor !== null) {
			const [a, b] = [Math.min(anchor, i), Math.max(anchor, i)]
			const on = !sel.has(rows[i].file)
			for (let k = a; k <= b; k++) on ? next.add(rows[k].file) : next.delete(rows[k].file)
		} else {
			next.has(rows[i].file) ? next.delete(rows[i].file) : next.add(rows[i].file)
			setAnchor(i)
		}
		setSel(next)
	}
	const edit = (file: string, k: keyof Row, v: string) => setRows(rows.map(r => (r.file === file ? { ...r, [k]: v } : r)))
	const setAll = () => setRows(rows.map(r => (sel.has(r.file) ? { ...r, [field]: value } : r)))
	const renumber = () => {
		let n = parseInt(start, 10)
		if (!Number.isFinite(n)) return
		setRows(rows.map(r => (sel.has(r.file) ? { ...r, track: String(n++) } : r)))
	}
	// the moved rows (the selection when the dragged row is part of it) go before row `at`; numbers stay with the positions
	const move = (at: number) => {
		const moving = drag && sel.has(drag) ? sel : new Set(drag ? [drag] : [])
		const target = rows[at]
		if (!moving.size || (target && moving.has(target.file))) return
		const rest = rows.filter(r => !moving.has(r.file)), moved = rows.filter(r => moving.has(r.file))
		const pos = target ? rest.indexOf(target) : rest.length
		const order = [...rest.slice(0, pos), ...moved, ...rest.slice(pos)]
		setRows(order.map((r, i) => ({ ...r, disc: rows[i].disc, track: rows[i].track })))
	}
	const all = rows.length > 0 && sel.size === rows.length

	return (
		<div>
			<div className="sticky top-0 z-10 mb-2 flex flex-wrap items-center gap-2 rounded-xl bg-slate-100 p-2 text-sm">
				<span className="px-1 text-slate-600">{chosen.length ? `${chosen.length} selected` : 'Click the boxes (shift-click for a range) to select tracks'}</span>
				{chosen.length > 0 && (
					<>
						<select value={field} onChange={e => setField(e.target.value as keyof Row)} className="h-8 rounded-md border bg-white px-2 text-sm">
							{SETTABLE.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
						</select>
						<Input className="h-8 w-48" value={value} onChange={e => setValue(e.target.value)} placeholder="value for all selected" />
						<Button size="sm" variant="outline" onClick={setAll}>Set</Button>
						<span className="ml-2 text-slate-600">Renumber from</span>
						<Input type="number" min={0} className="h-8 w-16" value={start} onChange={e => setStart(e.target.value)} />
						<Button size="sm" variant="outline" onClick={renumber}>Renumber</Button>
						<Button size="sm" variant="ghost" onClick={() => setSel(new Set())}>Clear</Button>
					</>
				)}
			</div>
			<table className="w-full text-sm">
				<thead>
					<tr className="text-left text-xs text-slate-500">
						<th className="w-6" />
						<th className="w-6 pb-1"><input type="checkbox" className="accent-slate-800" checked={all} onChange={() => setSel(all ? new Set() : new Set(rows.map(r => r.file)))} title="Select all" /></th>
						{COLS.map(c => <th key={c[0]} className="pb-1 font-medium">{c[1]}</th>)}
						<th />
					</tr>
				</thead>
				<tbody onDragLeave={() => setOver(null)}>
					{rows.map((r, i) => (
						<tr
							key={r.file}
							className={`${sel.has(r.file) ? 'bg-sky-50' : ''} ${drag && sel.has(r.file) && sel.size > 1 && sel.has(drag) ? 'opacity-60' : r.file === drag ? 'opacity-40' : ''} ${over === i ? 'shadow-[0_-2px_0_0_#1e293b]' : ''}`}
							onDragOver={e => { if (drag) { e.preventDefault(); setOver(i) } }}
							onDrop={e => { e.preventDefault(); move(i); setDrag(null); setOver(null) }}
						>
							<td className="cursor-grab pr-1 text-slate-400" draggable onDragStart={e => { setDrag(r.file); e.dataTransfer.effectAllowed = 'move' }} onDragEnd={() => { setDrag(null); setOver(null) }} title="Drag to reorder"><GripVertical className="size-4" /></td>
							<td className="pr-2"><input type="checkbox" className="accent-slate-800" checked={sel.has(r.file)} onChange={() => {}} onClick={e => click(e, i)} /></td>
							{COLS.map(([k, , w]) => (
								<td key={k} className="pb-1 pr-2"><Input className={`h-7 text-xs ${w}`} value={r[k] ?? ''} onChange={e => edit(r.file, k, e.target.value)} /></td>
							))}
							<td><button className="rounded-full p-1 hover:bg-slate-100" title="Edit lyrics" onClick={() => openLyrics(r.file)}><Pencil className="size-3" /></button></td>
						</tr>
					))}
					<tr onDragOver={e => { if (drag) { e.preventDefault(); setOver(rows.length) } }} onDrop={e => { e.preventDefault(); move(rows.length); setDrag(null); setOver(null) }} className={over === rows.length ? 'shadow-[0_-2px_0_0_#1e293b]' : ''}><td colSpan={8} className="h-4" /></tr>
				</tbody>
			</table>
		</div>
	)
}
