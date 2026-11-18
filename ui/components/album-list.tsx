'use client'

import { useEffect, useRef, useState } from 'react'
import { Album, STATUS, title } from '@/lib/api'

// A real data table: no covers, alternating rows, resizable and sortable columns (ADR 0086).
type SortKey = 'artist' | 'name' | 'media' | 'edition' | 'release_year' | 'master_year'
export type TableSort = { key: SortKey; dir: 1 | -1 }
const COLUMNS: { key: SortKey; label: string; width: number }[] = [
	{ key: 'artist', label: 'Album artist', width: 220 },
	{ key: 'name', label: 'Release name', width: 300 },
	{ key: 'media', label: 'Media', width: 90 },
	{ key: 'edition', label: 'Edition', width: 180 },
	{ key: 'release_year', label: 'Release year', width: 120 },
	{ key: 'master_year', label: 'Master year', width: 120 },
]
const FIELD: Record<SortKey, (a: Album) => string> = {
	artist: a => a.artist,
	name: title,
	media: a => a.media,
	edition: a => a.edition_name,
	release_year: a => a.release_year,
	master_year: a => a.master_year,
}
const NUMERIC: SortKey[] = ['release_year', 'master_year']
const MIN_WIDTH = 64
const STORE = 'tagwright-table-widths'
const DOT = { needs: 'bg-rose-600', ready: 'bg-sky-600', fixed: 'bg-emerald-600' }
const defaults = () => Object.fromEntries(COLUMNS.map(c => [c.key, c.width])) as Record<SortKey, number>

/** Empty values sort last in both directions; years compare numerically. */
export function tableCompare(sort: TableSort, a: Album, b: Album): number {
	const av = FIELD[sort.key](a), bv = FIELD[sort.key](b)
	if (!av && bv) return 1
	if (av && !bv) return -1
	if (!av && !bv) return 0
	const r = NUMERIC.includes(sort.key) ? Number(av) - Number(bv) : av.localeCompare(bv)
	return sort.dir * r
}

type Props = {
	albums: Album[]
	selected: string | null
	onSelect: (path: string) => void
	sort: TableSort | null
	onSort: (sort: TableSort) => void
}

export function AlbumList({ albums, selected, onSelect, sort, onSort }: Props) {
	const [widths, setWidths] = useState<Record<SortKey, number>>(() => {
		const w = defaults()
		if (typeof localStorage === 'undefined') return w
		try {
			const saved = JSON.parse(localStorage.getItem(STORE) || '{}')
			for (const c of COLUMNS) if (typeof saved[c.key] === 'number' && saved[c.key] >= MIN_WIDTH) w[c.key] = saved[c.key]
		} catch { /* a broken value just falls back to the defaults */ }
		return w
	})
	const drag = useRef<{ key: SortKey; x: number; width: number } | null>(null)

	useEffect(() => { localStorage.setItem(STORE, JSON.stringify(widths)) }, [widths])

	const startResize = (e: React.PointerEvent<HTMLSpanElement>, key: SortKey) => {
		e.preventDefault()
		e.stopPropagation()
		drag.current = { key, x: e.clientX, width: widths[key] }
		e.currentTarget.setPointerCapture(e.pointerId)
		document.body.style.cursor = 'col-resize'
		document.body.style.userSelect = 'none'
	}
	const moveResize = (e: React.PointerEvent<HTMLSpanElement>) => {
		if (!drag.current) return
		const { key, x, width } = drag.current
		setWidths(w => ({ ...w, [key]: Math.max(MIN_WIDTH, width + e.clientX - x) }))
	}
	const endResize = () => {
		drag.current = null
		document.body.style.cursor = ''
		document.body.style.userSelect = ''
	}
	const clickHeader = (key: SortKey) => onSort({ key, dir: sort?.key === key && sort.dir === 1 ? -1 : 1 })

	return (
		<div className="overflow-auto rounded-2xl border border-slate-200">
			<table className="w-full table-fixed border-collapse text-left text-[13px]" style={{ minWidth: COLUMNS.reduce((n, c) => n + widths[c.key], 0) }}>
				<colgroup>{COLUMNS.map(c => <col key={c.key} style={{ width: widths[c.key] }} />)}</colgroup>
				<thead>
					<tr className="bg-slate-100 text-xs text-slate-600">
						{COLUMNS.map(c => (
							<th key={c.key} scope="col" aria-sort={sort?.key === c.key ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none'} className="relative border-b border-slate-200 px-3 py-2 font-medium">
								<button type="button" onClick={() => clickHeader(c.key)} className="flex w-full items-center gap-1 truncate text-left hover:text-slate-900" title={`Sort by ${c.label}`}>
									{c.label}{sort?.key === c.key && <span aria-hidden="true" className="text-slate-500">{sort.dir === 1 ? '▲' : '▼'}</span>}
								</button>
								<span role="separator" aria-orientation="vertical" aria-label={`Resize ${c.label}`} title={`Drag to resize ${c.label}`}
									onPointerDown={e => startResize(e, c.key)} onPointerMove={moveResize} onPointerUp={endResize} onPointerCancel={endResize}
									className="absolute -right-1 top-0 z-10 h-full w-2 cursor-col-resize hover:bg-slate-300" />
							</th>
						))}
					</tr>
				</thead>
				<tbody>
					{albums.map((a, i) => (
						<tr key={a.path} tabIndex={0} aria-selected={a.path === selected}
							onClick={() => onSelect(a.path)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(a.path) } }}
							className={`cursor-pointer ${a.path === selected ? 'bg-slate-200' : i % 2 ? 'bg-slate-50' : 'bg-white'} hover:bg-slate-100`}>
							<td className="truncate px-3 py-2" title={a.artist}><span title={STATUS[a.status]} className={`mr-2 inline-block size-2 rounded-full ${DOT[a.status]}`} />{a.artist || 'No artist'}</td>
							<td className="truncate px-3 py-2 font-medium" title={title(a)}>{title(a)}</td>
							<td className="truncate px-3 py-2 text-slate-600" title={a.media}>{a.media}</td>
							<td className="truncate px-3 py-2 text-slate-600" title={a.edition_name}>{a.edition_name}</td>
							<td className="truncate px-3 py-2 tabular-nums text-slate-600">{a.release_year}</td>
							<td className="truncate px-3 py-2 tabular-nums text-slate-600">{a.master_year}</td>
						</tr>
					))}
				</tbody>
			</table>
		</div>
	)
}
